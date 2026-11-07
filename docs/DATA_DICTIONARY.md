# Step 1: Data Dictionary & Entity-Relationship Specification

**System:** Warehouse Zone Telemetry, Cold-Chain Compliance & Risk Alerting Platform  
**Fixed Seed:** `20261022`  
**ID / Nomenclature Conventions:**
- Warehouse: `WH-001` (`^WH-\d{3}$`)
- Zone: `ZONE-<warehouse-id>-001` (e.g., `ZONE-WH-001-001`, `^ZONE-WH-\d{3}-\d{3}$`)
- Sensor: `SNS-<zone-id>-<TYPE>-01` (e.g., `SNS-ZONE-WH-001-001-TEMP-01`, `^SNS-ZONE-WH-\d{3}-\d{3}-(TEMP|HUM|OCC|DOOR)-\d{2}$`)
- SensorReading: `RDG-<sensor-id>-<timestamp>` (e.g., `RDG-SNS-ZONE-WH-001-001-TEMP-01-20261022T080000Z`)
- DoorEvent: `DOR-<zone-id>-<timestamp>-<seq>` (e.g., `DOR-ZONE-WH-001-001-20261022T081500Z-001`)
- StorageRequirement: `REQ-001` (`^REQ-\d{3}$`)
- InventoryLot: `LOT-2026-000001` (`^LOT-2026-\d{6}$`)
- ZoneLotAssignment (Bridge Table): `ZLA-2026-000001` (`^ZLA-2026-\d{6}$`)
- Alarm: `ALM-2026-000001` (`^ALM-2026-\d{6}$`)
- AlarmAffectedLot (Bridge Table): `AAL-2026-000001` (`^AAL-2026-\d{6}$`)
- Inspection: `INS-2026-000001` (`^INS-2026-\d{6}$`)
- Remediation: `REM-2026-000001` (`^REM-2026-\d{6}$`)
- SensorZoneMappingHistory (Bridge/Audit Table): `SZM-2026-000001` (`^SZM-2026-\d{6}$`)

---

## 1. Entity Relationship & Cardinality Matrix

| Parent Entity | Child / Related Entity | Cardinality | Relationship Type | Foreign Key(s) | Optionality | Lifecycle / History Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `Warehouse` | `Zone` | `1 : N` | Hierarchical Containment | `Zone.warehouse_id -> Warehouse.warehouse_id` | Mandatory parent | Zones belong to exactly 1 Warehouse |
| `Zone` | `Sensor` | `1 : N` (Baseline) / `N : M` (via `SensorZoneMappingHistory`) | Physical Placement + Audit Bridge | `Sensor.primary_zone_id -> Zone.zone_id` | Mandatory parent | Edge case `SENSOR_MULTI_ZONE_NO_RATIONALE` maps a sensor across multiple zones without rationale |
| `Sensor` | `SensorReading` | `1 : N` | Time-series Telemetry Stream | `SensorReading.sensor_id -> Sensor.sensor_id` | Mandatory parent | Append-only immutable telemetry log |
| `Zone` | `DoorEvent` | `1 : N` | Physical Access / Door State | `DoorEvent.zone_id -> Zone.zone_id`, `DoorEvent.sensor_id -> Sensor.sensor_id` | Mandatory `zone_id`, Optional `sensor_id` | Captures `OPEN`, `CLOSE`, `HELD_OPEN` transitions |
| `StorageRequirement` | `InventoryLot` | `1 : N` | Product Compliance Policy | `InventoryLot.requirement_id -> StorageRequirement.requirement_id` | Mandatory parent | Defines allowed temp/humidity envelope & max excursion dwell |
| `Zone` <-> `InventoryLot` | `ZoneLotAssignment` | `N : M` (Bridge) | Lot Storage & Dwell History | `zone_id -> Zone.zone_id`, `lot_id -> InventoryLot.lot_id` | Mandatory FKs | Preserves lot movement history & calculates `dwell_hours` from timestamps |
| `Zone` / `Sensor` | `Alarm` | `1 : N` | Risk Detection & Alerting | `Alarm.zone_id -> Zone.zone_id`, `Alarm.trigger_sensor_id -> Sensor.sensor_id` | Mandatory `zone_id`, Optional `trigger_sensor_id` | Triggered by excursion, door held open, sensor outage/gap, or incompatible zone |
| `Alarm` <-> `InventoryLot` | `AlarmAffectedLot` | `N : M` (Bridge) | Traceability & Impact Linkage | `alarm_id -> Alarm.alarm_id`, `lot_id -> InventoryLot.lot_id` | Mandatory FKs | Links alarms to overlapping lots by zone + timestamp window |
| `Alarm` / `Zone` | `Inspection` | `1 : N` | Quality & Maintenance Verification | `Inspection.alarm_id -> Alarm.alarm_id`, `Inspection.zone_id -> Zone.zone_id` | Mandatory `alarm_id` and `zone_id` | Triggered by Alarm; scheduled audits require an associated audit event |
| `Inspection` / `InventoryLot` | `Remediation` | `1 : N` | Corrective Action & Lot Disposition | `Remediation.inspection_id -> Inspection.inspection_id`, `Remediation.affected_lot_id -> InventoryLot.lot_id` | Mandatory `inspection_id`, Optional `affected_lot_id` | Links remediation directly to financial & inventory quantity impact |

---

## 2. Granular Entity Data Dictionary

### 2.1 `Warehouse` (Master Table)
| Field | Type | Req/Opt | Allowed Values / Format | Units | Unique | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `warehouse_id` | `VARCHAR(16)` | Required | `WH-001` .. `WH-010` (`^WH-\d{3}$`) | N/A | PK (Unique) | Non-null, immutable deterministic format |
| `warehouse_name` | `VARCHAR(100)` | Required | Non-empty string | N/A | Yes | Length 3..100 |
| `region` | `VARCHAR(32)` | Required | `NA-EAST`, `NA-WEST`, `EU-CENTRAL`, `APAC-SOUTH`, `LATAM-NORTH` | N/A | No | Enum membership check |
| `facility_type` | `VARCHAR(32)` | Required | `COLD_STORAGE`, `PHARMA_GDP`, `MIXED_DISTRIBUTION`, `AMBIENT_BULK` | N/A | No | Enum membership check |
| `total_capacity_pallets` | `INTEGER` | Required | `1000` .. `50000` | `pallets` | No | Must equal `SUM(Zone.capacity_pallets)` for child zones |
| `active_zone_count` | `INTEGER` | Required | `1` .. `50` | `zones` | No | Derived: count of `ACTIVE` child zones |
| `lifecycle_state` | `VARCHAR(24)` | Required | `ACTIVE`, `MAINTENANCE`, `DECOMMISSIONED` | N/A | No | Valid lifecycle state enum |
| `effective_from` | `TIMESTAMP` | Required | ISO-8601 UTC (`YYYY-MM-DDTHH:MM:SSZ`) | `UTC` | No | `effective_from <= effective_to` (when `effective_to` present) |
| `effective_to` | `TIMESTAMP` | Optional | ISO-8601 UTC or `NULL` | `UTC` | No | `NULL` if `lifecycle_state = ACTIVE` |

### 2.2 `Zone` (Master Table)
| Field | Type | Req/Opt | Allowed Values / Format | Units | Unique | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `zone_id` | `VARCHAR(32)` | Required | `ZONE-<warehouse-id>-001` (`^ZONE-WH-\d{3}-\d{3}$`) | N/A | PK (Unique) | Prefix must match `warehouse_id` |
| `warehouse_id` | `VARCHAR(16)` | Required | Valid `Warehouse.warehouse_id` | N/A | No (FK) | Referential integrity to `Warehouse` |
| `zone_name` | `VARCHAR(100)` | Required | Non-empty string | N/A | No | Length 3..100 |
| `zone_type` | `VARCHAR(24)` | Required | `DEEP_FREEZE`, `CHILLED`, `CONTROLLED_AMBIENT`, `HEATED_CURING`, `STAGING_DOCK` | N/A | No | Enum membership check |
| `temp_min_c` | `DECIMAL(6,2)` | Required | `-40.00` .. `45.00` | `°C` | No | `temp_min_c < temp_max_c` |
| `temp_max_c` | `DECIMAL(6,2)` | Required | `-35.00` .. `60.00` | `°C` | No | `temp_max_c > temp_min_c` |
| `humidity_min_pct` | `DECIMAL(5,2)` | Required | `10.00` .. `85.00` | `%RH` | No | `humidity_min_pct < humidity_max_pct` |
| `humidity_max_pct` | `DECIMAL(5,2)` | Required | `25.00` .. `98.00` | `%RH` | No | `humidity_max_pct <= 100.0` |
| `max_occupancy_persons` | `INTEGER` | Required | `2` .. `50` | `persons` | No | `> 0` |
| `capacity_pallets` | `INTEGER` | Required | `50` .. `2500` | `pallets` | No | `> 0` |
| `lifecycle_state` | `VARCHAR(24)` | Required | `ACTIVE`, `QUARANTINED`, `MAINTENANCE`, `INACTIVE` | N/A | No | Valid lifecycle state enum |
| `effective_from` | `TIMESTAMP` | Required | ISO-8601 UTC | `UTC` | No | `>= Warehouse.effective_from` |

### 2.3 `Sensor` (Master Table)
| Field | Type | Req/Opt | Allowed Values / Format | Units | Unique | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `sensor_id` | `VARCHAR(48)` | Required | `SNS-<zone-id>-<TYPE>-<NN>` | N/A | PK (Unique) | Must match `^SNS-ZONE-WH-\d{3}-\d{3}-(TEMP|HUM|OCC|DOOR)-\d{2}$` |
| `primary_zone_id` | `VARCHAR(32)` | Required | Valid `Zone.zone_id` | N/A | No (FK) | Referential integrity to `Zone` |
| `sensor_type` | `VARCHAR(16)` | Required | `TEMP`, `HUM`, `OCC`, `DOOR` | N/A | No | Must match `<TYPE>` token in `sensor_id` |
| `unit` | `VARCHAR(16)` | Required | `CELSIUS`, `PERCENT_RH`, `COUNT`, `STATE` | N/A | No | Aligned with `sensor_type` |
| `sampling_interval_sec` | `INTEGER` | Required | `60`, `300`, `900` | `seconds` | No | Allowed sampling interval |
| `drift_rate_per_day` | `DECIMAL(6,4)` | Required | `-0.5000` .. `0.5000` | `unit/day` | No | Models realistic calibration drift |
| `calibration_due_date` | `DATE` | Required | ISO Date (`YYYY-MM-DD`) | `date` | No | Valid calendar date |
| `lifecycle_state` | `VARCHAR(24)` | Required | `ACTIVE`, `DRIFTING`, `OUTAGE`, `DECOMMISSIONED` | N/A | No | Valid lifecycle state enum |
| `installed_at` | `TIMESTAMP` | Required | ISO-8601 UTC | `UTC` | No | `>= Zone.effective_from` |

### 2.4 `SensorZoneMappingHistory` (Bridge / Audit Table for N:M Sensor-to-Zone Placement)
| Field | Type | Req/Opt | Allowed Values / Format | Units | Unique | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `mapping_id` | `VARCHAR(24)` | Required | `SZM-2026-000001` (`^SZM-2026-\d{6}$`) | N/A | PK (Unique) | Zero-padded counter |
| `sensor_id` | `VARCHAR(48)` | Required | Valid `Sensor.sensor_id` | N/A | No (FK) | Referential integrity to `Sensor` |
| `zone_id` | `VARCHAR(32)` | Required | Valid `Zone.zone_id` | N/A | No (FK) | Referential integrity to `Zone` |
| `mapping_rationale` | `VARCHAR(120)` | Optional | `INITIAL_INSTALL`, `BOUNDARY_SHARED_DUCT`, `RELOCATION`, or `NULL` | N/A | No | Required when a sensor is active in >1 zone; `NULL` flags edge case `SENSOR_MULTI_ZONE_NO_RATIONALE` |
| `effective_from` | `TIMESTAMP` | Required | ISO-8601 UTC | `UTC` | No | Valid timestamp |
| `effective_to` | `TIMESTAMP` | Optional | ISO-8601 UTC or `NULL` | `UTC` | No | `effective_to >= effective_from` |

### 2.5 `SensorReading` (Event / Telemetry Table)
| Field | Type | Req/Opt | Allowed Values / Format | Units | Unique | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `reading_id` | `VARCHAR(80)` | Required | `RDG-<sensor-id>-<timestamp>` | N/A | PK (Unique) | Deterministic concatenation of sensor_id & compact UTC timestamp |
| `sensor_id` | `VARCHAR(48)` | Required | Valid `Sensor.sensor_id` | N/A | No (FK) | Referential integrity to `Sensor` |
| `zone_id` | `VARCHAR(32)` | Required | Valid `Zone.zone_id` | N/A | No (FK) | Referential integrity to `Zone` |
| `recorded_at` | `TIMESTAMP` | Required | ISO-8601 UTC | `UTC` | No | Monotonically ordered per sensor |
| `value` | `DECIMAL(8,3)` | Required | `-60.0` .. `100.0` | `°C / %RH / persons / door state` | No | Within physical sensor limits; door state is `0` (closed) or `1` (open) |
| `unit` | `VARCHAR(16)` | Required | `CELSIUS`, `PERCENT_RH`, `COUNT` | N/A | No | Matches parent `Sensor.unit` |
| `delta_prev_sec` | `INTEGER` | Required | `>= 0` | `seconds` | No | Derived: `recorded_at - prev(recorded_at)` for same sensor |
| `is_excursion` | `BOOLEAN` | Required | `true`, `false` | N/A | No | Derived: `true` if `value` outside `Zone` threshold range |
| `is_gap_after_prev` | `BOOLEAN` | Required | `true`, `false` | N/A | No | Derived: `delta_prev_sec > 2 * Sensor.sampling_interval_sec`; deliberately false only for separately labeled silent-gap anomalies |
| `quality_status` | `VARCHAR(24)` | Required | `VALID`, `DRIFT_SUSPECT`, `EXCURSION`, `GAP_RECOVERED`, `NORMALIZED_GAP` | N/A | No | Allowed enum |

### 2.6 `DoorEvent` (Event Table)
| Field | Type | Req/Opt | Allowed Values / Format | Units | Unique | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `door_event_id` | `VARCHAR(64)` | Required | `DOR-<zone-id>-<timestamp>-<seq>` | N/A | PK (Unique) | Deterministic ID |
| `zone_id` | `VARCHAR(32)` | Required | Valid `Zone.zone_id` | N/A | No (FK) | Referential integrity to `Zone` |
| `sensor_id` | `VARCHAR(48)` | Optional | Valid `Sensor.sensor_id` (`DOOR` type) | N/A | No (FK) | Referential integrity to `Sensor` |
| `opened_at` | `TIMESTAMP` | Required | ISO-8601 UTC | `UTC` | No | `opened_at <= closed_at` |
| `closed_at` | `TIMESTAMP` | Optional | ISO-8601 UTC or `NULL` | `UTC` | No | `>= opened_at` |
| `open_duration_sec` | `INTEGER` | Required | `1` .. `14400` | `seconds` | No | Derived: `closed_at - opened_at` |
| `trigger_actor` | `VARCHAR(32)` | Required | `FORKLIFT_LOADING`, `OPERATOR_ENTRY`, `MAINTENANCE_ACCESS`, `PROPPED_OPEN_FAULT` | N/A | No | Allowed enum |
| `caused_excursion` | `BOOLEAN` | Required | `true`, `false` | N/A | No | `true` if `open_duration_sec >= 300` and zone temp/humidity drifted |

### 2.7 `StorageRequirement` (Master Policy Table)
| Field | Type | Req/Opt | Allowed Values / Format | Units | Unique | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `requirement_id` | `VARCHAR(16)` | Required | `REQ-001` .. `REQ-012` (`^REQ-\d{3}$`) | N/A | PK (Unique) | Deterministic ID |
| `product_category` | `VARCHAR(64)` | Required | `BIOLOGIC_VACCINE_ULT`, `FROZEN_BIOPHARMA`, `CHILLED_INSULIN`, `DAIRY_PROBIOTIC`, `CONTROLLED_API_POWDER`, `HEATED_RESIN_CURING` | N/A | Yes | Allowed category |
| `req_temp_min_c` | `DECIMAL(6,2)` | Required | `-40.00` .. `45.00` | `°C` | No | `< req_temp_max_c` |
| `req_temp_max_c` | `DECIMAL(6,2)` | Required | `-15.00` .. `60.00` | `°C` | No | `> req_temp_min_c` |
| `req_humidity_min_pct` | `DECIMAL(5,2)` | Required | `15.00` .. `75.00` | `%RH` | No | `< req_humidity_max_pct` |
| `req_humidity_max_pct` | `DECIMAL(5,2)` | Required | `35.00` .. `90.00` | `%RH` | No | `<= 100.0` |
| `max_excursion_minutes` | `INTEGER` | Required | `15` .. `240` | `minutes` | No | `> 0` |
| `allowed_zone_types` | `VARCHAR(100)` | Required | Comma-delimited `Zone.zone_type` values | N/A | No | Valid zone_type tokens |

### 2.8 `InventoryLot` (Transaction / Master Table)
| Field | Type | Req/Opt | Allowed Values / Format | Units | Unique | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `lot_id` | `VARCHAR(24)` | Required | `LOT-2026-000001` (`^LOT-2026-\d{6}$`) | N/A | PK (Unique) | Deterministic 6-digit padded ID |
| `requirement_id` | `VARCHAR(16)` | Required | Valid `StorageRequirement.requirement_id` | N/A | No (FK) | Referential integrity to `StorageRequirement` |
| `current_zone_id` | `VARCHAR(32)` | Required | Valid `Zone.zone_id` | N/A | No (FK) | Referential integrity to `Zone` |
| `product_sku` | `VARCHAR(32)` | Required | `SKU-<CAT>-<NNN>` | N/A | No | Non-empty string |
| `initial_quantity_units` | `INTEGER` | Required | `50` .. `5000` | `units` | No | `> 0` |
| `compromised_quantity_units` | `INTEGER` | Required | `0` .. `initial_quantity_units` | `units` | No | Derived: `SUM(Remediation.scrapped_units)` for this lot |
| `available_quantity_units` | `INTEGER` | Required | `0` .. `initial_quantity_units` | `units` | No | Derived arithmetic: `initial_quantity_units - compromised_quantity_units` |
| `unit_value_usd` | `DECIMAL(10,2)` | Required | `10.00` .. `1500.00` | `USD` | No | `> 0` |
| `total_dwell_hours` | `DECIMAL(8,2)` | Required | `>= 0.0` | `hours` | No | Derived: `SUM(ZoneLotAssignment.dwell_hours)` |
| `cumulative_excursion_min` | `INTEGER` | Required | `>= 0` | `minutes` | No | Derived from overlapping excursion alarms in assigned zone |
| `lifecycle_state` | `VARCHAR(24)` | Required | `STORED`, `QUARANTINED`, `INSPECTED_RELEASED`, `SCRAPPED`, `SHIPPED` | N/A | No | Valid lifecycle transition |
| `received_at` | `TIMESTAMP` | Required | ISO-8601 UTC | `UTC` | No | `<= expiration_date` |
| `expiration_date` | `DATE` | Required | ISO Date (`YYYY-MM-DD`) | `date` | No | `> received_at` |

### 2.9 `ZoneLotAssignment` (Bridge Table: `Zone` N:M `InventoryLot`)
| Field | Type | Req/Opt | Allowed Values / Format | Units | Unique | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `assignment_id` | `VARCHAR(24)` | Required | `ZLA-2026-000001` (`^ZLA-2026-\d{6}$`) | N/A | PK (Unique) | Deterministic ID |
| `lot_id` | `VARCHAR(24)` | Required | Valid `InventoryLot.lot_id` | N/A | No (FK) | Referential integrity to `InventoryLot` |
| `zone_id` | `VARCHAR(32)` | Required | Valid `Zone.zone_id` | N/A | No (FK) | Referential integrity to `Zone` |
| `entered_at` | `TIMESTAMP` | Required | ISO-8601 UTC | `UTC` | No | `>= InventoryLot.received_at` |
| `exited_at` | `TIMESTAMP` | Optional | ISO-8601 UTC or `NULL` for current placement | `UTC` | No | If present, `> entered_at` |
| `dwell_hours` | `DECIMAL(8,2)` | Required | `>= 0` | `hours` | No | Derived from entered/exited timestamps; zero for an open placement |
| `is_zone_compatible` | `BOOLEAN` | Required | `true`, `false` | N/A | No | Derived: checks if `Zone.zone_type` in `StorageRequirement.allowed_zone_types` |

### 2.10 `Alarm` (Event / Exception Table)
| Field | Type | Req/Opt | Allowed Values / Format | Units | Unique | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `alarm_id` | `VARCHAR(24)` | Required | `ALM-2026-000001` (`^ALM-2026-\d{6}$`) | N/A | PK (Unique) | Deterministic ID |
| `zone_id` | `VARCHAR(32)` | Required | Valid `Zone.zone_id` | N/A | No (FK) | Referential integrity to `Zone` |
| `trigger_sensor_id` | `VARCHAR(48)` | Optional | Valid `Sensor.sensor_id` or `NULL` | N/A | No (FK) | Referential integrity to `Sensor` |
| `alarm_type` | `VARCHAR(32)` | Required | `TEMP_EXCURSION_HIGH`, `TEMP_EXCURSION_LOW`, `HUMIDITY_EXCURSION`, `DOOR_HELD_OPEN`, `SENSOR_OUTAGE_GAP`, `SENSOR_DRIFT`, `INCOMPATIBLE_LOT_ZONE`, `OCCUPANCY_OVER_LIMIT` | N/A | No | Allowed enum |
| `severity` | `VARCHAR(16)` | Required | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` | N/A | No | Derived from magnitude & duration of threshold breach |
| `triggered_at` | `TIMESTAMP` | Required | ISO-8601 UTC | `UTC` | No | `<= resolved_at` |
| `resolved_at` | `TIMESTAMP` | Optional | ISO-8601 UTC or `NULL` | `UTC` | No | `>= triggered_at` |
| `duration_minutes` | `INTEGER` | Required | `>= 1` | `minutes` | No | Derived: `(resolved_at - triggered_at) / 60` |
| `peak_value` | `DECIMAL(8,3)` | Required | Numeric reading | `sensor unit` | No | Derived from max/min triggering `SensorReading.value` |
| `threshold_limit` | `DECIMAL(8,3)` | Required | Numeric threshold | `sensor unit` | No | Matches `Zone` threshold limit |
| `affected_lot_count` | `INTEGER` | Required | `>= 0` | `lots` | No | Derived: count of rows in `AlarmAffectedLot` for `alarm_id` |
| `lifecycle_state` | `VARCHAR(24)` | Required | `OPEN`, `ACKNOWLEDGED`, `INVESTIGATING`, `RESOLVED`, `CLOSED` | N/A | No | Valid lifecycle state |

### 2.11 `AlarmAffectedLot` (Bridge Table: `Alarm` N:M `InventoryLot`)
| Field | Type | Req/Opt | Allowed Values / Format | Units | Unique | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `alarm_lot_id` | `VARCHAR(24)` | Required | `AAL-2026-000001` (`^AAL-2026-\d{6}$`) | N/A | PK (Unique) | Deterministic ID |
| `alarm_id` | `VARCHAR(24)` | Required | Valid `Alarm.alarm_id` | N/A | No (FK) | Referential integrity to `Alarm` |
| `lot_id` | `VARCHAR(24)` | Required | Valid `InventoryLot.lot_id` | N/A | No (FK) | Referential integrity to `InventoryLot` |
| `overlap_minutes` | `INTEGER` | Required | `>= 1` | `minutes` | No | Derived overlap between `Alarm` window and `ZoneLotAssignment` window |
| `risk_score` | `DECIMAL(5,2)` | Required | `0.00` .. `100.00` | `score` | No | Derived from excursion magnitude and `overlap_minutes / max_excursion_minutes` |

### 2.12 `Inspection` (Event / Workflow Table)
| Field | Type | Req/Opt | Allowed Values / Format | Units | Unique | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `inspection_id` | `VARCHAR(24)` | Required | `INS-2026-000001` (`^INS-2026-\d{6}$`) | N/A | PK (Unique) | Deterministic ID |
| `alarm_id` | `VARCHAR(24)` | Required | Valid `Alarm.alarm_id` | N/A | No (FK) | Referential integrity to `Alarm` |
| `zone_id` | `VARCHAR(32)` | Required | Valid `Zone.zone_id` | N/A | No (FK) | Must equal `Alarm.zone_id` |
| `inspector_role` | `VARCHAR(32)` | Required | `QUALITY_ENGINEER`, `MAINTENANCE_ENGINEER`, `PLANT_OPERATOR`, `OT_IT_ADMIN` | N/A | No | Primary Actor enum |
| `inspected_at` | `TIMESTAMP` | Required | ISO-8601 UTC | `UTC` | No | `>= Alarm.triggered_at` |
| `finding_code` | `VARCHAR(32)` | Required | `CONFIRMED_EXCURSION`, `DOOR_SEAL_FAILURE`, `SENSOR_CALIBRATION_DRIFT`, `SENSOR_COMMS_DROP`, `WRONG_ZONE_PLACEMENT`, `WITHIN_TOLERANCE` | N/A | No | Allowed enum |
| `requires_remediation` | `BOOLEAN` | Required | `true`, `false` | N/A | No | `true` for severe/critical findings |
| `lifecycle_state` | `VARCHAR(24)` | Required | `SCHEDULED`, `IN_PROGRESS`, `COMPLETED` | N/A | No | Valid lifecycle state |

### 2.13 `Remediation` (Outcome / Action Table)
| Field | Type | Req/Opt | Allowed Values / Format | Units | Unique | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `remediation_id` | `VARCHAR(24)` | Required | `REM-2026-000001` (`^REM-2026-\d{6}$`) | N/A | PK (Unique) | Deterministic ID |
| `inspection_id` | `VARCHAR(24)` | Required | Valid `Inspection.inspection_id` | N/A | No (FK) | Referential integrity to `Inspection` |
| `alarm_id` | `VARCHAR(24)` | Required | Valid `Alarm.alarm_id` | N/A | No (FK) | Referential integrity to `Alarm` |
| `affected_lot_id` | `VARCHAR(24)` | Optional | Valid `InventoryLot.lot_id` or `NULL` | N/A | No (FK) | Referential integrity to `InventoryLot` |
| `action_type` | `VARCHAR(32)` | Required | `RELOCATE_LOT`, `QUARANTINE_AND_SCRAP_PARTIAL`, `RECALIBRATE_SENSOR`, `REPAIR_DOOR_CLOSER`, `RESTORE_SENSOR_LINK`, `RELEASE_LOT_AFTER_TEST` | N/A | No | Allowed enum |
| `scrapped_units` | `INTEGER` | Required | `0` .. `5000` | `units` | No | `<= InventoryLot.initial_quantity_units` |
| `financial_impact_usd` | `DECIMAL(12,2)` | Required | `>= 0.00` | `USD` | No | Derived: `scrapped_units * InventoryLot.unit_value_usd + labor_cost_usd` |
| `labor_cost_usd` | `DECIMAL(10,2)` | Required | `50.00` .. `2500.00` | `USD` | No | `> 0` |
| `completed_at` | `TIMESTAMP` | Required | ISO-8601 UTC | `UTC` | No | `>= Inspection.inspected_at` |
| `lifecycle_state` | `VARCHAR(24)` | Required | `PENDING`, `EXECUTED`, `VERIFIED_CLOSED` | N/A | No | Valid lifecycle state |

---

## 3. Separate Ground-Truth Labels (`ground_truth.csv` / `ground_truth.json`)

Per **Step 5** and **Step 7**, deliberate anomaly and edge cases are recorded in a separate `ground_truth.csv` / `ground_truth.json` file (and **never** leaked as a column inside input tables):

| `issue_type` Code | Required Scenario | Target Entity Type | Detection Rule & Expected System Decision |
| :--- | :--- | :--- | :--- |
| `LOT_INCOMPATIBLE_ZONE` | Lot assigned to incompatible zone | `InventoryLot` / `ZoneLotAssignment` | `Zone.zone_type` is not in `StorageRequirement.allowed_zone_types` (e.g., `BIOLOGIC_VACCINE_ULT` requiring `DEEP_FREEZE` placed in `CONTROLLED_AMBIENT`). Expected decision: `REJECT_ASSIGNMENT_QUARANTINE_LOT`. |
| `SENSOR_MULTI_ZONE_NO_RATIONALE` | Sensor mapped to multiple zones without rationale | `Sensor` / `SensorZoneMappingHistory` | Same `sensor_id` has `>= 2` overlapping active rows in `SensorZoneMappingHistory` with `mapping_rationale IS NULL`. Expected decision: `FLAG_INVALID_TOPOLOGY_AUDIT`. |
| `READING_GAP_TREATED_AS_NORMAL` | Reading gap treated as normal | `SensorReading` / `Sensor` | Consecutive readings have `delta_prev_sec > 2 * sampling_interval_sec` (e.g., 3-hour outage gap), yet `is_gap_after_prev = false` and `quality_status = NORMALIZED_GAP` without generating a `SENSOR_OUTAGE_GAP` alarm. Expected decision: `RAISE_MISSING_TELEMETRY_GAP_ALARM`. |
| `ALARM_UNLINKED_TO_AFFECTED_LOTS` | Alarm not linked to affected lots | `Alarm` | `Alarm` occurred in a `zone_id` while active `ZoneLotAssignment` records overlapped `[triggered_at, resolved_at]`, yet `AlarmAffectedLot` has `0` linked rows (`affected_lot_count = 0`). Expected decision: `BACKFILL_AFFECTED_LOT_LINKS_AND_QUARANTINE`. |
