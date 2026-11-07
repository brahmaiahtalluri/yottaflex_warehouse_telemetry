#!/usr/bin/env python3
"""
Step 2–9: Deterministic Synthetic Data Generator for Warehouse Zone Telemetry & Risk Alerting
=============================================================================================
Fixed Seed Default: 20261022
Supported Scales:
  --scale starter : 10 Warehouses, 100 Zones, 500 Sensors, 15,000 Readings, 500 Lots (fast demo/Git bundle)
  --scale full    : 10 Warehouses, 100 Zones, 500 Sensors, 1,000,000 Readings, 10,000 Lots (full benchmark volume)

Covers all 10 Core Entities + 3 Bridge Tables:
  1. Warehouse (WH-001 .. WH-010)
  2. Zone (ZONE-WH-001-001 .. ZONE-WH-010-010)
  3. Sensor (SNS-ZONE-WH-001-001-TEMP-01 ..)
  4. SensorZoneMappingHistory (SZM-2026-000001 ..) [Bridge/Audit N:M]
  5. SensorReading (RDG-<sensor-id>-<timestamp>)
  6. DoorEvent (DOR-<zone-id>-<timestamp>-<seq>)
  7. StorageRequirement (REQ-001 .. REQ-006)
  8. InventoryLot (LOT-2026-000001 ..)
  9. ZoneLotAssignment (ZLA-2026-000001 ..) [Bridge N:M]
  10. Alarm (ALM-2026-000001 ..)
  11. AlarmAffectedLot (AAL-2026-000001 ..) [Bridge N:M]
  12. Inspection (INS-2026-000001 ..)
  13. Remediation (REM-2026-000001 ..)

Also produces separate ground_truth.csv & ground_truth.json (Step 7) with 4 required edge cases:
  - LOT_INCOMPATIBLE_ZONE
  - SENSOR_MULTI_ZONE_NO_RATIONALE
  - READING_GAP_TREATED_AS_NORMAL
  - ALARM_UNLINKED_TO_AFFECTED_LOTS
"""

import argparse
import csv
import datetime
import hashlib
import json
import os
import random
import time
from typing import Dict, List, Any, Tuple

FIXED_SEED_DEFAULT = 20261022
BASE_EPOCH = datetime.datetime(2026, 10, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)

REGIONS = ["NA-EAST", "NA-WEST", "EU-CENTRAL", "APAC-SOUTH", "LATAM-NORTH"]
FACILITY_TYPES = ["COLD_STORAGE", "PHARMA_GDP", "MIXED_DISTRIBUTION", "AMBIENT_BULK"]

ZONE_TYPE_SPECS = [
    ("DEEP_FREEZE", -30.0, -18.0, 25.0, 55.0, 6),
    ("CHILLED", 2.0, 8.0, 35.0, 65.0, 12),
    ("CONTROLLED_AMBIENT", 15.0, 25.0, 30.0, 60.0, 20),
    ("HEATED_CURING", 30.0, 42.0, 20.0, 50.0, 8),
    ("STAGING_DOCK", 8.0, 22.0, 35.0, 75.0, 25),
]

STORAGE_REQUIREMENTS = [
    {
        "requirement_id": "REQ-001",
        "product_category": "BIOLOGIC_VACCINE_ULT",
        "req_temp_min_c": -30.0,
        "req_temp_max_c": -18.0,
        "req_humidity_min_pct": 25.0,
        "req_humidity_max_pct": 55.0,
        "max_excursion_minutes": 20,
        "allowed_zone_types": "DEEP_FREEZE",
        "sku_prefix": "SKU-VAX",
        "base_unit_value": 420.00,
    },
    {
        "requirement_id": "REQ-002",
        "product_category": "FROZEN_BIOPHARMA",
        "req_temp_min_c": -28.0,
        "req_temp_max_c": -18.0,
        "req_humidity_min_pct": 25.0,
        "req_humidity_max_pct": 60.0,
        "max_excursion_minutes": 30,
        "allowed_zone_types": "DEEP_FREEZE",
        "sku_prefix": "SKU-BIO",
        "base_unit_value": 280.00,
    },
    {
        "requirement_id": "REQ-003",
        "product_category": "CHILLED_INSULIN",
        "req_temp_min_c": 2.0,
        "req_temp_max_c": 8.0,
        "req_humidity_min_pct": 35.0,
        "req_humidity_max_pct": 65.0,
        "max_excursion_minutes": 45,
        "allowed_zone_types": "CHILLED",
        "sku_prefix": "SKU-INS",
        "base_unit_value": 165.00,
    },
    {
        "requirement_id": "REQ-004",
        "product_category": "DAIRY_PROBIOTIC",
        "req_temp_min_c": 2.0,
        "req_temp_max_c": 8.0,
        "req_humidity_min_pct": 35.0,
        "req_humidity_max_pct": 70.0,
        "max_excursion_minutes": 60,
        "allowed_zone_types": "CHILLED,STAGING_DOCK",
        "sku_prefix": "SKU-PRO",
        "base_unit_value": 45.00,
    },
    {
        "requirement_id": "REQ-005",
        "product_category": "CONTROLLED_API_POWDER",
        "req_temp_min_c": 15.0,
        "req_temp_max_c": 25.0,
        "req_humidity_min_pct": 30.0,
        "req_humidity_max_pct": 60.0,
        "max_excursion_minutes": 90,
        "allowed_zone_types": "CONTROLLED_AMBIENT,STAGING_DOCK",
        "sku_prefix": "SKU-API",
        "base_unit_value": 190.00,
    },
    {
        "requirement_id": "REQ-006",
        "product_category": "HEATED_RESIN_CURING",
        "req_temp_min_c": 30.0,
        "req_temp_max_c": 42.0,
        "req_humidity_min_pct": 20.0,
        "req_humidity_max_pct": 50.0,
        "max_excursion_minutes": 60,
        "allowed_zone_types": "HEATED_CURING",
        "sku_prefix": "SKU-RSN",
        "base_unit_value": 85.00,
    },
]


def iso_utc(dt: datetime.datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def compact_utc(dt: datetime.datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


def parse_iso(ts: str) -> datetime.datetime:
    return datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)


def generate_dataset(seed: int, scale: str, out_dir: str, export_sql: bool = True) -> Dict[str, Any]:
    t0 = time.time()
    rng = random.Random(seed)

    # Scale configuration
    num_warehouses = 10
    zones_per_wh = 10  # 100 zones total
    sensors_per_zone = 5  # 500 sensors total (TEMP-01, TEMP-02, HUM-01, OCC-01, DOOR-01)
    if scale == "full":
        readings_per_sensor = 2000  # 500 * 2,000 = 1,000,000 readings
        num_lots = 10000
    else:
        readings_per_sensor = 30  # 500 * 30 = 15,000 readings for fast git/UI loading
        num_lots = 500

    os.makedirs(out_dir, exist_ok=True)
    csv_dir = os.path.join(out_dir, "csv")
    json_dir = os.path.join(out_dir, "json")
    os.makedirs(csv_dir, exist_ok=True)
    os.makedirs(json_dir, exist_ok=True)

    ground_truth: List[Dict[str, Any]] = []
    gt_counter = 0

    def add_ground_truth(issue_type: str, entity_type: str, entity_id: str, zone_id: str,
                         related_id: str, expected_decision: str, description: str, detected_at: str):
        nonlocal gt_counter
        gt_counter += 1
        ground_truth.append({
            "ground_truth_id": f"GT-2026-{gt_counter:06d}",
            "issue_type": issue_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "zone_id": zone_id,
            "related_entity_id": related_id,
            "expected_decision": expected_decision,
            "severity": "CRITICAL" if "INCOMPATIBLE" in issue_type or "UNLINKED" in issue_type else "HIGH",
            "detected_at": detected_at,
            "description": description,
        })

    # =========================================================================
    # 1. Master Table: Warehouse & Zone (with derived capacity reconciliation)
    # =========================================================================
    warehouses: List[Dict[str, Any]] = []
    zones: List[Dict[str, Any]] = []
    zones_by_type: Dict[str, List[Dict[str, Any]]] = {spec[0]: [] for spec in ZONE_TYPE_SPECS}
    zone_lookup: Dict[str, Dict[str, Any]] = {}

    city_names = [
        "Newark Cold Hub", "Chicago Pharma Depot", "Dallas Distribution Center",
        "Atlanta Biologics Vault", "Phoenix Thermal Annex", "Frankfurt GDP Hub",
        "Rotterdam Port Coldstore", "Singapore BioLogix", "Hyderabad Vaccine Center",
        "Monterrey Industrial Hub"
    ]

    for w_idx in range(1, num_warehouses + 1):
        wh_id = f"WH-{w_idx:03d}"
        wh_eff = BASE_EPOCH - datetime.timedelta(days=180 - w_idx * 5)
        wh_zones: List[Dict[str, Any]] = []

        for z_idx in range(1, zones_per_wh + 1):
            zone_id = f"ZONE-{wh_id}-{z_idx:03d}"
            spec = ZONE_TYPE_SPECS[(z_idx - 1) % len(ZONE_TYPE_SPECS)]
            z_type, t_min, t_max, h_min, h_max, max_occ = spec
            cap_pallets = rng.choice([150, 200, 250, 300, 400, 500])
            z_state = "ACTIVE" if z_idx <= 9 else rng.choice(["ACTIVE", "MAINTENANCE"])
            z_eff = wh_eff + datetime.timedelta(days=1)

            zone_rec = {
                "zone_id": zone_id,
                "warehouse_id": wh_id,
                "zone_name": f"{wh_id} {z_type.replace('_', ' ').title()} Bay {z_idx:02d}",
                "zone_type": z_type,
                "temp_min_c": round(t_min, 2),
                "temp_max_c": round(t_max, 2),
                "humidity_min_pct": round(h_min, 2),
                "humidity_max_pct": round(h_max, 2),
                "max_occupancy_persons": max_occ,
                "capacity_pallets": cap_pallets,
                "lifecycle_state": z_state,
                "effective_from": iso_utc(z_eff),
            }
            zones.append(zone_rec)
            wh_zones.append(zone_rec)
            zones_by_type[z_type].append(zone_rec)
            zone_lookup[zone_id] = zone_rec

        # Step 6: Derived warehouse totals from child zones
        total_cap = sum(z["capacity_pallets"] for z in wh_zones)
        active_cnt = sum(1 for z in wh_zones if z["lifecycle_state"] == "ACTIVE")

        warehouses.append({
            "warehouse_id": wh_id,
            "warehouse_name": f"{city_names[w_idx - 1]} ({wh_id})",
            "region": REGIONS[(w_idx - 1) % len(REGIONS)],
            "facility_type": FACILITY_TYPES[(w_idx - 1) % len(FACILITY_TYPES)],
            "total_capacity_pallets": total_cap,
            "active_zone_count": active_cnt,
            "lifecycle_state": "ACTIVE",
            "effective_from": iso_utc(wh_eff),
            "effective_to": "",
        })

    # =========================================================================
    # 2. Master Table: Sensor & Bridge Table: SensorZoneMappingHistory
    # =========================================================================
    sensors: List[Dict[str, Any]] = []
    sensor_mappings: List[Dict[str, Any]] = []
    sensors_by_zone: Dict[str, List[Dict[str, Any]]] = {z["zone_id"]: [] for z in zones}
    szm_counter = 0

    sensor_templates = [
        ("TEMP", "01", "CELSIUS", 300),
        ("TEMP", "02", "CELSIUS", 300),
        ("HUM", "01", "PERCENT_RH", 300),
        ("OCC", "01", "COUNT", 300),
        ("DOOR", "01", "STATE", 60),
    ]

    # Select 6 sensors for Edge Case #2: SENSOR_MULTI_ZONE_NO_RATIONALE
    multi_zone_anomaly_indices = {7, 42, 108, 215, 330, 455}

    for z_idx, zone in enumerate(zones):
        z_id = zone["zone_id"]
        z_eff_dt = parse_iso(zone["effective_from"])
        for s_tmpl_idx, (s_type, s_num, s_unit, interval_sec) in enumerate(sensor_templates):
            global_s_idx = z_idx * sensors_per_zone + s_tmpl_idx + 1
            sensor_id = f"SNS-{z_id}-{s_type}-{s_num}"
            is_drifting = (global_s_idx % 23 == 0) and s_type in ("TEMP", "HUM")
            drift_rate = round(rng.uniform(0.12, 0.38), 4) if is_drifting else round(rng.uniform(-0.015, 0.015), 4)
            s_state = "DRIFTING" if is_drifting else "ACTIVE"
            install_dt = z_eff_dt + datetime.timedelta(hours=2)
            cal_due = (BASE_EPOCH + datetime.timedelta(days=rng.randint(30, 180))).strftime("%Y-%m-%d")

            s_rec = {
                "sensor_id": sensor_id,
                "primary_zone_id": z_id,
                "sensor_type": s_type,
                "unit": s_unit,
                "sampling_interval_sec": interval_sec,
                "drift_rate_per_day": drift_rate,
                "calibration_due_date": cal_due,
                "lifecycle_state": s_state,
                "installed_at": iso_utc(install_dt),
            }
            sensors.append(s_rec)
            sensors_by_zone[z_id].append(s_rec)

            # Primary baseline mapping
            szm_counter += 1
            sensor_mappings.append({
                "mapping_id": f"SZM-2026-{szm_counter:06d}",
                "sensor_id": sensor_id,
                "zone_id": z_id,
                "mapping_rationale": "INITIAL_INSTALL",
                "effective_from": iso_utc(install_dt),
                "effective_to": "",
            })

            # Inject Edge Case #2: Sensor mapped to multiple zones without rationale
            if global_s_idx in multi_zone_anomaly_indices:
                other_zone = zones[(z_idx + 1) % len(zones)]
                szm_counter += 1
                mapping_id = f"SZM-2026-{szm_counter:06d}"
                anom_dt = BASE_EPOCH + datetime.timedelta(hours=12)
                sensor_mappings.append({
                    "mapping_id": mapping_id,
                    "sensor_id": sensor_id,
                    "zone_id": other_zone["zone_id"],
                    "mapping_rationale": "",  # Missing rationale for concurrent multi-zone assignment!
                    "effective_from": iso_utc(anom_dt),
                    "effective_to": "",
                })
                add_ground_truth(
                    issue_type="SENSOR_MULTI_ZONE_NO_RATIONALE",
                    entity_type="Sensor",
                    entity_id=sensor_id,
                    zone_id=other_zone["zone_id"],
                    related_id=mapping_id,
                    expected_decision="FLAG_INVALID_TOPOLOGY_AUDIT",
                    description=(
                        f"Sensor {sensor_id} is concurrently mapped to primary zone {z_id} and secondary "
                        f"zone {other_zone['zone_id']} (mapping {mapping_id}) with empty mapping_rationale."
                    ),
                    detected_at=iso_utc(anom_dt),
                )

    # =========================================================================
    # 3. Master Table: StorageRequirement
    # =========================================================================
    storage_reqs: List[Dict[str, Any]] = []
    req_lookup: Dict[str, Dict[str, Any]] = {}
    for req in STORAGE_REQUIREMENTS:
        r_copy = {
            "requirement_id": req["requirement_id"],
            "product_category": req["product_category"],
            "req_temp_min_c": req["req_temp_min_c"],
            "req_temp_max_c": req["req_temp_max_c"],
            "req_humidity_min_pct": req["req_humidity_min_pct"],
            "req_humidity_max_pct": req["req_humidity_max_pct"],
            "max_excursion_minutes": req["max_excursion_minutes"],
            "allowed_zone_types": req["allowed_zone_types"],
        }
        storage_reqs.append(r_copy)
        req_lookup[req["requirement_id"]] = req

    # =========================================================================
    # 4. Event Table: DoorEvent & Scheduled Zone Excursions
    # =========================================================================
    door_events: List[Dict[str, Any]] = []
    # We schedule specific excursion windows per zone so DoorEvents, SensorReadings, Lots, and Alarms align!
    zone_excursion_windows: Dict[str, List[Dict[str, Any]]] = {z["zone_id"]: [] for z in zones}

    for z_idx, zone in enumerate(zones):
        z_id = zone["zone_id"]
        door_sensor = next(s for s in sensors_by_zone[z_id] if s["sensor_type"] == "DOOR")
        num_door_events = 3 if scale == "starter" else 8

        for d_seq in range(1, num_door_events + 1):
            offset_min = d_seq * 35 + (z_idx % 7) * 5
            opened_dt = BASE_EPOCH + datetime.timedelta(minutes=offset_min)
            # Every 5th zone on event 2 has a propped-open door causing a thermal/humidity excursion
            is_propped = (z_idx % 5 == 0 and d_seq == 2)
            if is_propped:
                open_dur_sec = rng.randint(540, 1200)  # 9 to 20 minutes open
                actor = "PROPPED_OPEN_FAULT"
                caused_exc = True
            else:
                open_dur_sec = rng.randint(35, 180)
                actor = rng.choice(["FORKLIFT_LOADING", "OPERATOR_ENTRY", "MAINTENANCE_ACCESS"])
                caused_exc = False

            closed_dt = opened_dt + datetime.timedelta(seconds=open_dur_sec)
            door_event_id = f"DOR-{z_id}-{compact_utc(opened_dt)}-{d_seq:03d}"

            door_events.append({
                "door_event_id": door_event_id,
                "zone_id": z_id,
                "sensor_id": door_sensor["sensor_id"],
                "opened_at": iso_utc(opened_dt),
                "closed_at": iso_utc(closed_dt),
                "open_duration_sec": open_dur_sec,
                "trigger_actor": actor,
                "caused_excursion": caused_exc,
            })

            if caused_exc:
                zone_excursion_windows[z_id].append({
                    "start_dt": opened_dt,
                    "end_dt": closed_dt + datetime.timedelta(minutes=15),
                    "door_event_id": door_event_id,
                    "temp_spike_c": round(rng.uniform(4.5, 9.5), 2),
                    "hum_spike_pct": round(rng.uniform(12.0, 22.0), 2),
                })

    # =========================================================================
    # 5. Event Table: SensorReading (with Excursions, Sensor Outages, and Edge Case #3)
    # =========================================================================
    # Edge Case #3: Reading gap treated as normal (normalised silent gap on specific sensors)
    silent_gap_sensor_indices = {3, 58, 143, 268, 393, 478}
    # Legitimate outage sensors (properly flagged as gap + alarm)
    explicit_outage_sensor_indices = {11, 86, 191, 311, 416}

    sensor_readings: List[Dict[str, Any]] = []
    detected_excursion_events: List[Dict[str, Any]] = []
    detected_outage_events: List[Dict[str, Any]] = []

    for s_idx, sensor in enumerate(sensors):
        s_id = sensor["sensor_id"]
        z_id = sensor["primary_zone_id"]
        zone = zone_lookup[z_id]
        s_type = sensor["sensor_type"]
        s_unit = sensor["unit"]
        interval_sec = sensor["sampling_interval_sec"]
        drift_rate = sensor["drift_rate_per_day"]

        t_mid = (zone["temp_min_c"] + zone["temp_max_c"]) / 2.0
        h_mid = (zone["humidity_min_pct"] + zone["humidity_max_pct"]) / 2.0
        exc_windows = zone_excursion_windows[z_id]

        curr_dt = BASE_EPOCH
        prev_dt = None
        peak_exc_val = None
        exc_start_dt = None
        exc_end_dt = None

        for r_step in range(readings_per_sensor):
            is_silent_gap_step = ((s_idx + 1) in silent_gap_sensor_indices and r_step == 12)
            is_explicit_outage_step = ((s_idx + 1) in explicit_outage_sensor_indices and r_step == 14)

            if r_step == 0:
                curr_dt = BASE_EPOCH
                delta_sec = 0
            elif is_silent_gap_step or is_explicit_outage_step:
                # 45-minute telemetry drop (9x normal 300s interval)
                gap_Jump_sec = interval_sec * 9
                curr_dt = prev_dt + datetime.timedelta(seconds=gap_Jump_sec)
                delta_sec = gap_Jump_sec
            else:
                curr_dt = prev_dt + datetime.timedelta(seconds=interval_sec)
                delta_sec = interval_sec

            # Compute physical reading value
            in_exc_window = any(w["start_dt"] <= curr_dt <= w["end_dt"] for w in exc_windows)
            days_elapsed = (curr_dt - BASE_EPOCH).total_seconds() / 86400.0
            drift_offset = drift_rate * days_elapsed * 10.0

            if s_type == "TEMP":
                val = t_mid + rng.uniform(-1.1, 1.1) + drift_offset
                if in_exc_window:
                    val = zone["temp_max_c"] + rng.uniform(3.2, 7.8)
                val = round(val, 3)
                is_exc = (val < zone["temp_min_c"] or val > zone["temp_max_c"])
            elif s_type == "HUM":
                val = h_mid + rng.uniform(-3.0, 3.0) + drift_offset
                if in_exc_window:
                    val = min(99.0, zone["humidity_max_pct"] + rng.uniform(8.0, 16.0))
                val = round(val, 3)
                is_exc = (val < zone["humidity_min_pct"] or val > zone["humidity_max_pct"])
            elif s_type == "OCC":
                occ_val = rng.randint(0, max(1, zone["max_occupancy_persons"] - 1))
                if z_idx_from_id(z_id) % 14 == 0 and r_step == 18:
                    occ_val = zone["max_occupancy_persons"] + 4
                val = float(occ_val)
                is_exc = occ_val > zone["max_occupancy_persons"]
            else:  # DOOR sensor state (0.0 closed, 1.0 open)
                val = 1.0 if in_exc_window else 0.0
                is_exc = False

            # Track excursion window per sensor for Alarm generation
            if is_exc:
                if exc_start_dt is None:
                    exc_start_dt = curr_dt
                    peak_exc_val = val
                else:
                    peak_exc_val = max(peak_exc_val, val)
                exc_end_dt = curr_dt

            # Determine gap status
            actual_gap = (r_step > 0 and delta_sec > 2 * interval_sec)
            reading_id = f"RDG-{s_id}-{compact_utc(curr_dt)}"

            if is_silent_gap_step:
                # Edge Case #3: Reading gap treated as normal!
                is_gap_flag = False
                q_status = "NORMALIZED_GAP"
                add_ground_truth(
                    issue_type="READING_GAP_TREATED_AS_NORMAL",
                    entity_type="SensorReading",
                    entity_id=reading_id,
                    zone_id=z_id,
                    related_id=s_id,
                    expected_decision="RAISE_MISSING_TELEMETRY_GAP_ALARM",
                    description=(
                        f"Reading {reading_id} on sensor {s_id} has delta_prev_sec={delta_sec}s "
                        f"(expected {interval_sec}s), but is_gap_after_prev=false and no outage alarm was raised."
                    ),
                    detected_at=iso_utc(curr_dt),
                )
            elif actual_gap:
                is_gap_flag = True
                q_status = "GAP_RECOVERED"
                detected_outage_events.append({
                    "sensor_id": s_id,
                    "zone_id": z_id,
                    "reading_id": reading_id,
                    "triggered_at": prev_dt + datetime.timedelta(seconds=interval_sec * 2),
                    "resolved_at": curr_dt,
                    "gap_seconds": delta_sec,
                    "interval_sec": interval_sec,
                })
            elif is_exc:
                is_gap_flag = False
                q_status = "EXCURSION"
            elif sensor["lifecycle_state"] == "DRIFTING":
                is_gap_flag = False
                q_status = "DRIFT_SUSPECT"
            else:
                is_gap_flag = False
                q_status = "VALID"

            sensor_readings.append({
                "reading_id": reading_id,
                "sensor_id": s_id,
                "zone_id": z_id,
                "recorded_at": iso_utc(curr_dt),
                "value": val,
                "unit": s_unit,
                "delta_prev_sec": delta_sec,
                "is_excursion": is_exc,
                "is_gap_after_prev": is_gap_flag,
                "quality_status": q_status,
            })
            prev_dt = curr_dt

        if exc_start_dt is not None and s_type in ("TEMP", "HUM", "OCC"):
            if s_type == "TEMP":
                a_type = "TEMP_EXCURSION_HIGH"
                thresh = zone["temp_max_c"]
            elif s_type == "HUM":
                a_type = "HUMIDITY_EXCURSION"
                thresh = zone["humidity_max_pct"]
            else:
                a_type = "OCCUPANCY_OVER_LIMIT"
                thresh = float(zone["max_occupancy_persons"])

            detected_excursion_events.append({
                "zone_id": z_id,
                "sensor_id": s_id,
                "alarm_type": a_type,
                "triggered_at": exc_start_dt,
                "resolved_at": exc_end_dt + datetime.timedelta(minutes=5),
                "peak_value": peak_exc_val,
                "threshold_limit": thresh,
            })

    # =========================================================================
    # 6. InventoryLot & ZoneLotAssignment (with Edge Case #1: Incompatible Zone)
    # =========================================================================
    inventory_lots: List[Dict[str, Any]] = []
    zone_lot_assignments: List[Dict[str, Any]] = []
    lots_by_zone: Dict[str, List[Dict[str, Any]]] = {z["zone_id"]: [] for z in zones}
    zla_by_zone: Dict[str, List[Dict[str, Any]]] = {z["zone_id"]: [] for z in zones}
    zla_counter = 0

    # Inject 8 lots into Edge Case #1: LOT_INCOMPATIBLE_ZONE
    incompatible_lot_indices = {15, 65, 135, 205, 275, 345, 415, 485}

    for l_idx in range(1, num_lots + 1):
        lot_id = f"LOT-2026-{l_idx:06d}"
        req = STORAGE_REQUIREMENTS[(l_idx - 1) % len(STORAGE_REQUIREMENTS)]
        allowed_types = req["allowed_zone_types"].split(",")

        is_incompat_anomaly = (l_idx in incompatible_lot_indices)
        if is_incompat_anomaly:
            # Deliberately assign to an incompatible zone type (e.g. DEEP_FREEZE lot into HEATED_CURING or CONTROLLED_AMBIENT)
            incompatible_candidates = [
                z for z in zones if z["zone_type"] not in allowed_types
            ]
            chosen_zone = incompatible_candidates[l_idx % len(incompatible_candidates)]
        else:
            compatible_candidates = zones_by_type[allowed_types[0]]
            chosen_zone = compatible_candidates[l_idx % len(compatible_candidates)]

        z_id = chosen_zone["zone_id"]
        received_dt = BASE_EPOCH - datetime.timedelta(hours=rng.randint(12, 72))
        entered_dt = received_dt + datetime.timedelta(minutes=30)
        exited_dt = BASE_EPOCH + datetime.timedelta(hours=rng.randint(24, 120))
        dwell_hrs = round((exited_dt - entered_dt).total_seconds() / 3600.0, 2)
        is_compat = (chosen_zone["zone_type"] in allowed_types)

        zla_counter += 1
        assignment_id = f"ZLA-2026-{zla_counter:06d}"
        zla_rec = {
            "assignment_id": assignment_id,
            "lot_id": lot_id,
            "zone_id": z_id,
            "entered_at": iso_utc(entered_dt),
            "exited_at": iso_utc(exited_dt),
            "dwell_hours": dwell_hrs,
            "is_zone_compatible": is_compat,
            "_entered_dt": entered_dt,
            "_exited_dt": exited_dt,
        }
        zone_lot_assignments.append(zla_rec)
        zla_by_zone[z_id].append(zla_rec)

        init_qty = rng.choice([200, 400, 500, 800, 1000, 1500])
        unit_val = round(req["base_unit_value"] * rng.uniform(0.9, 1.15), 2)
        exp_date = (BASE_EPOCH + datetime.timedelta(days=rng.randint(90, 540))).strftime("%Y-%m-%d")

        lot_rec = {
            "lot_id": lot_id,
            "requirement_id": req["requirement_id"],
            "current_zone_id": z_id,
            "product_sku": f"{req['sku_prefix']}-{(l_idx % 90) + 10:03d}",
            "initial_quantity_units": init_qty,
            "compromised_quantity_units": 0,  # Reconciled from Remediations in Step 6
            "available_quantity_units": init_qty,  # Reconciled in Step 6
            "unit_value_usd": unit_val,
            "total_dwell_hours": dwell_hrs,  # Reconciled from ZoneLotAssignment
            "cumulative_excursion_min": 0,  # Reconciled from overlapping Alarms
            "lifecycle_state": "QUARANTINED" if is_incompat_anomaly else "STORED",
            "received_at": iso_utc(received_dt),
            "expiration_date": exp_date,
        }
        inventory_lots.append(lot_rec)
        lots_by_zone[z_id].append(lot_rec)

        if is_incompat_anomaly:
            add_ground_truth(
                issue_type="LOT_INCOMPATIBLE_ZONE",
                entity_type="InventoryLot",
                entity_id=lot_id,
                zone_id=z_id,
                related_id=assignment_id,
                expected_decision="REJECT_ASSIGNMENT_QUARANTINE_LOT",
                description=(
                    f"Lot {lot_id} ({req['product_category']}, requires {req['allowed_zone_types']}) "
                    f"was assigned to incompatible zone {z_id} ({chosen_zone['zone_type']})."
                ),
                detected_at=iso_utc(entered_dt),
            )

    lot_lookup = {l["lot_id"]: l for l in inventory_lots}

    # =========================================================================
    # 7. Alarm, AlarmAffectedLot, Inspection & Remediation (with Edge Case #4)
    # =========================================================================
    alarms: List[Dict[str, Any]] = []
    alarm_affected_lots: List[Dict[str, Any]] = []
    inspections: List[Dict[str, Any]] = []
    remediations: List[Dict[str, Any]] = []

    alm_counter = 0
    aal_counter = 0
    ins_counter = 0
    rem_counter = 0

    # Combine excursion events + explicit sensor outages into candidate alarms
    raw_alarm_candidates: List[Dict[str, Any]] = []
    for ev in detected_excursion_events:
        raw_alarm_candidates.append(ev)
    for out_ev in detected_outage_events:
        raw_alarm_candidates.append({
            "zone_id": out_ev["zone_id"],
            "sensor_id": out_ev["sensor_id"],
            "alarm_type": "SENSOR_OUTAGE_GAP",
            "triggered_at": out_ev["triggered_at"],
            "resolved_at": out_ev["resolved_at"],
            "peak_value": float(out_ev["gap_seconds"]),
            "threshold_limit": float(out_ev["interval_sec"] * 2),
        })

    # Select 5 alarms for Edge Case #4: ALARM_UNLINKED_TO_AFFECTED_LOTS
    unlinked_alarm_indices = {2, 7, 13, 19, 25}

    for idx, cand in enumerate(raw_alarm_candidates, start=1):
        alm_counter += 1
        alarm_id = f"ALM-2026-{alm_counter:06d}"
        z_id = cand["zone_id"]
        trig_dt = cand["triggered_at"]
        res_dt = cand["resolved_at"]
        dur_min = max(1, int((res_dt - trig_dt).total_seconds() // 60))

        if cand["alarm_type"] in ("TEMP_EXCURSION_HIGH", "SENSOR_OUTAGE_GAP") and dur_min >= 15:
            sev = "CRITICAL"
        elif cand["alarm_type"] in ("TEMP_EXCURSION_HIGH", "HUMIDITY_EXCURSION"):
            sev = "HIGH"
        else:
            sev = "MEDIUM"

        # Find overlapping lots in this zone during [trig_dt, res_dt]
        overlapping_zlas = [
            zla for zla in zla_by_zone[z_id]
            if zla["_entered_dt"] < res_dt and zla["_exited_dt"] > trig_dt
        ]

        is_unlinked_anomaly = (idx in unlinked_alarm_indices and len(overlapping_zlas) > 0)
        linked_lots_for_this_alarm: List[Dict[str, Any]] = []

        if is_unlinked_anomaly:
            # Edge Case #4: Alarm not linked to affected lots despite active overlapping lots in zone!
            first_missing_lot = overlapping_zlas[0]["lot_id"]
            add_ground_truth(
                issue_type="ALARM_UNLINKED_TO_AFFECTED_LOTS",
                entity_type="Alarm",
                entity_id=alarm_id,
                zone_id=z_id,
                related_id=first_missing_lot,
                expected_decision="BACKFILL_AFFECTED_LOT_LINKS_AND_QUARANTINE",
                description=(
                    f"Alarm {alarm_id} ({cand['alarm_type']}) in zone {z_id} overlapped with "
                    f"{len(overlapping_zlas)} stored inventory lot(s) including {first_missing_lot}, "
                    f"but has 0 rows in AlarmAffectedLot."
                ),
                detected_at=iso_utc(trig_dt),
            )
        else:
            for zla in overlapping_zlas:
                aal_counter += 1
                lot_obj = lot_lookup[zla["lot_id"]]
                req_obj = req_lookup[lot_obj["requirement_id"]]
                overlap_start = max(trig_dt, zla["_entered_dt"])
                overlap_end = min(res_dt, zla["_exited_dt"])
                overlap_min = max(1, int((overlap_end - overlap_start).total_seconds() // 60))
                risk_score = min(100.0, round((overlap_min / req_obj["max_excursion_minutes"]) * 75.0, 2))
                aal_rec = {
                    "alarm_lot_id": f"AAL-2026-{aal_counter:06d}",
                    "alarm_id": alarm_id,
                    "lot_id": zla["lot_id"],
                    "overlap_minutes": overlap_min,
                    "risk_score": risk_score,
                }
                alarm_affected_lots.append(aal_rec)
                linked_lots_for_this_alarm.append(aal_rec)
                # Accumulate excursion minutes on the lot
                if "EXCURSION" in cand["alarm_type"]:
                    lot_obj["cumulative_excursion_min"] += overlap_min

        alarm_rec = {
            "alarm_id": alarm_id,
            "zone_id": z_id,
            "trigger_sensor_id": cand["sensor_id"],
            "alarm_type": cand["alarm_type"],
            "severity": sev,
            "triggered_at": iso_utc(trig_dt),
            "resolved_at": iso_utc(res_dt),
            "duration_minutes": dur_min,
            "peak_value": round(cand["peak_value"], 3),
            "threshold_limit": round(cand["threshold_limit"], 3),
            "affected_lot_count": len(linked_lots_for_this_alarm),
            "lifecycle_state": "RESOLVED",
        }
        alarms.append(alarm_rec)

        # Generate Inspection for every Alarm
        ins_counter += 1
        inspection_id = f"INS-2026-{ins_counter:06d}"
        insp_dt = trig_dt + datetime.timedelta(minutes=10)
        if cand["alarm_type"] == "SENSOR_OUTAGE_GAP":
            role = "OT_IT_ADMIN"
            finding = "SENSOR_COMMS_DROP"
        elif "EXCURSION" in cand["alarm_type"]:
            role = "QUALITY_ENGINEER"
            finding = "CONFIRMED_EXCURSION"
        else:
            role = "PLANT_OPERATOR"
            finding = "WITHIN_TOLERANCE"

        req_rem = (sev in ("CRITICAL", "HIGH") or len(linked_lots_for_this_alarm) > 0)
        inspections.append({
            "inspection_id": inspection_id,
            "alarm_id": alarm_id,
            "zone_id": z_id,
            "inspector_role": role,
            "inspected_at": iso_utc(insp_dt),
            "finding_code": finding,
            "requires_remediation": req_rem,
            "lifecycle_state": "COMPLETED",
        })

        # Generate Remediation when required, linking directly to affected lot & inventory impact
        if req_rem:
            rem_counter += 1
            rem_id = f"REM-2026-{rem_counter:06d}"
            comp_dt = insp_dt + datetime.timedelta(minutes=25)
            target_lot_id = linked_lots_for_this_alarm[0]["lot_id"] if linked_lots_for_this_alarm else ""
            labor_usd = round(rng.choice([150.0, 250.0, 400.0, 600.0]), 2)

            if target_lot_id and sev == "CRITICAL":
                lot_obj = lot_lookup[target_lot_id]
                scrapped = min(lot_obj["available_quantity_units"] // 5, 60)
                action = "QUARANTINE_AND_SCRAP_PARTIAL"
                fin_impact = round(scrapped * lot_obj["unit_value_usd"] + labor_usd, 2)
                # Reconcile lot quantities (Step 6)
                lot_obj["compromised_quantity_units"] += scrapped
                lot_obj["available_quantity_units"] = (
                    lot_obj["initial_quantity_units"] - lot_obj["compromised_quantity_units"]
                )
                lot_obj["lifecycle_state"] = "QUARANTINED"
            elif target_lot_id:
                scrapped = 0
                action = "RELEASE_LOT_AFTER_TEST"
                fin_impact = labor_usd
                lot_lookup[target_lot_id]["lifecycle_state"] = "INSPECTED_RELEASED"
            else:
                scrapped = 0
                action = "RESTORE_SENSOR_LINK" if cand["alarm_type"] == "SENSOR_OUTAGE_GAP" else "REPAIR_DOOR_CLOSER"
                fin_impact = labor_usd

            remediations.append({
                "remediation_id": rem_id,
                "inspection_id": inspection_id,
                "alarm_id": alarm_id,
                "affected_lot_id": target_lot_id,
                "action_type": action,
                "scrapped_units": scrapped,
                "financial_impact_usd": fin_impact,
                "labor_cost_usd": labor_usd,
                "completed_at": iso_utc(comp_dt),
                "lifecycle_state": "VERIFIED_CLOSED",
            })

    # Strip internal helper keys from zone_lot_assignments
    for zla in zone_lot_assignments:
        zla.pop("_entered_dt", None)
        zla.pop("_exited_dt", None)

    # =========================================================================
    # 8. Export CSV, JSON, Separate Ground Truth, SQL Seed & Source Manifest
    # =========================================================================
    tables = {
        "warehouses": warehouses,
        "zones": zones,
        "sensors": sensors,
        "sensor_zone_mapping_history": sensor_mappings,
        "sensor_readings": sensor_readings,
        "door_events": door_events,
        "storage_requirements": storage_reqs,
        "inventory_lots": inventory_lots,
        "zone_lot_assignments": zone_lot_assignments,
        "alarms": alarms,
        "alarm_affected_lots": alarm_affected_lots,
        "inspections": inspections,
        "remediations": remediations,
    }

    file_checksums: Dict[str, str] = {}
    row_counts: Dict[str, int] = {}

    for t_name, rows in tables.items():
        row_counts[t_name] = len(rows)
        csv_path = os.path.join(csv_dir, f"{t_name}.csv")
        write_csv_deterministic(csv_path, rows)
        file_checksums[f"csv/{t_name}.csv"] = sha256_file(csv_path)

        json_path = os.path.join(json_dir, f"{t_name}.json")
        with open(json_path, "w", encoding="utf-8", newline="\n") as jf:
            if scale == "full" and t_name == "sensor_readings":
                json.dump(rows, jf, separators=(",", ":"))
            else:
                json.dump(rows, jf, indent=2)
        file_checksums[f"json/{t_name}.json"] = sha256_file(json_path)

    # Separate ground_truth.csv and ground_truth.json (Step 7)
    gt_csv_path = os.path.join(out_dir, "ground_truth.csv")
    gt_json_path = os.path.join(out_dir, "ground_truth.json")
    write_csv_deterministic(gt_csv_path, ground_truth)
    with open(gt_json_path, "w", encoding="utf-8", newline="\n") as gjf:
        json.dump(ground_truth, gjf, indent=2)
    file_checksums["ground_truth.csv"] = sha256_file(gt_csv_path)
    file_checksums["ground_truth.json"] = sha256_file(gt_json_path)
    row_counts["ground_truth"] = len(ground_truth)

    # Export complete SQL seed data for both scales.
    if export_sql:
        sql_seed_path = os.path.join(out_dir, "seed_data.sql")
        write_sql_seed(sql_seed_path, tables)
        file_checksums["seed_data.sql"] = sha256_file(sql_seed_path)

    manifest = {
        "generator_version": "1.0.0",
        "fixed_seed": seed,
        "scale": scale,
        "base_epoch_utc": iso_utc(BASE_EPOCH),
        "generator_command": f"python3 generator/generate_dataset.py --seed {seed} --scale {scale} --out-dir {out_dir}",
        "provenance": {
            "data_origin": "100% Synthetic Deterministic Generation (Lawful Use / Zero PII)",
            "schema_inspiration": [
                "WHO Technical Supplement: Temperature Mapping of Storage Areas (Public Guidance)",
                "EU GDP Guidelines (2013/C 343/01) for Cold-Chain Pharmaceutical Warehousing",
                "ISA-95 / ISA-18.2 Industrial Alarm Management Lifecycle Standards"
            ],
            "license": "MIT / Open Challenge Submission",
        },
        "row_counts": row_counts,
        "edge_case_counts": count_by_issue_type(ground_truth),
        "file_sha256_checksums": file_checksums,
        "generation_elapsed_sec": round(time.time() - t0, 3),
    }

    manifest_path = os.path.join(out_dir, "source_manifest.json")
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as mf:
        json.dump(manifest, mf, indent=2)

    return manifest


def z_idx_from_id(zone_id: str) -> int:
    # ZONE-WH-001-001 -> integer index
    parts = zone_id.split("-")
    return (int(parts[2]) - 1) * 10 + int(parts[3])


def count_by_issue_type(gt_rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for r in gt_rows:
        it = r["issue_type"]
        counts[it] = counts.get(it, 0) + 1
    return counts


def write_csv_deterministic(path: str, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def sql_val(v: Any) -> str:
    if v is None or v == "":
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("'", "''")
    return f"'{s}'"


def write_sql_seed(path: str, tables: Dict[str, List[Dict[str, Any]]]) -> None:
    sql_table_map = [
        ("warehouses", "warehouse"),
        ("zones", "warehouse_zone"),
        ("sensors", "sensor"),
        ("sensor_zone_mapping_history", "sensor_zone_mapping_history"),
        ("sensor_readings", "sensor_reading"),
        ("storage_requirements", "storage_requirement"),
        ("inventory_lots", "inventory_lot"),
        ("zone_lot_assignments", "zone_lot_assignment"),
        ("door_events", "door_event"),
        ("alarms", "alarm"),
        ("alarm_affected_lots", "alarm_affected_lot"),
        ("inspections", "inspection"),
        ("remediations", "remediation"),
    ]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("-- Deterministic SQL Seed Data (Seed: 20261022)\n")
        for dict_key, sql_tbl in sql_table_map:
            rows = tables.get(dict_key, [])
            if not rows:
                continue
            cols = list(rows[0].keys())
            col_list = ", ".join(cols)
            f.write(f"\n-- Table: {sql_tbl} ({len(rows)} rows)\n")
            for r in rows:
                vals = ", ".join(sql_val(r[c]) for c in cols)
                f.write(f"INSERT INTO {sql_tbl} ({col_list}) VALUES ({vals});\n")


def main():
    parser = argparse.ArgumentParser(description="Deterministic Warehouse Telemetry Dataset Generator")
    parser.add_argument("--seed", type=int, default=FIXED_SEED_DEFAULT, help="Fixed RNG seed (default: 20261022)")
    parser.add_argument("--scale", choices=["starter", "full"], default="starter", help="Dataset scale")
    parser.add_argument("--out-dir", type=str, default="data/seed", help="Output directory")
    args = parser.parse_args()

    manifest = generate_dataset(seed=args.seed, scale=args.scale, out_dir=args.out_dir)
    print(json.dumps({
        "status": "SUCCESS",
        "seed": manifest["fixed_seed"],
        "scale": manifest["scale"],
        "row_counts": manifest["row_counts"],
        "edge_case_counts": manifest["edge_case_counts"],
        "elapsed_sec": manifest["generation_elapsed_sec"],
    }, indent=2))


if __name__ == "__main__":
    main()
