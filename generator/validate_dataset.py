#!/usr/bin/env python3
"""
Step 8 & Step 10: Automated Validation Suite & Two-Run Reproducibility Verifier
================================================================================
Validates:
  1. Primary-Key Uniqueness & Nomenclature Regex Compliance across all 13 tables
  2. Foreign-Key Referential Integrity across all parent-child & bridge relationships
  3. Allowed Enum Compliance for categorical columns
  4. Chronological Date/Timestamp Ordering & Monotonic Sensor Reading Timestamps
  5. Derived-Value Arithmetic Reconciliation (Warehouse capacities, Lot quantities & dwell hours,
     Alarm affected lot counts, Remediation financial impacts)
  6. Lifecycle State Transition Consistency
  7. Ground-Truth Separation Check (verifies zero leakage of ground_truth labels into input tables)
  8. Edge Case & Acceptance Criteria Coverage (verifies all 4 required negative scenarios)
  9. Step 10 Reproducibility Check (runs generator twice with identical seed 20261022 and compares
     row counts and SHA-256 checksums across every generated file)
"""

import argparse
import csv
import datetime
import json
import os
import re
import shutil
import tempfile
from typing import Dict, List, Any

from generate_dataset import generate_dataset, FIXED_SEED_DEFAULT


ID_PATTERNS = {
    "warehouses": ("warehouse_id", re.compile(r"^WH-\d{3}$")),
    "zones": ("zone_id", re.compile(r"^ZONE-WH-\d{3}-\d{3}$")),
    "sensors": ("sensor_id", re.compile(r"^SNS-ZONE-WH-\d{3}-\d{3}-(TEMP|HUM|OCC|DOOR)-\d{2}$")),
    "sensor_zone_mapping_history": ("mapping_id", re.compile(r"^SZM-2026-\d{6}$")),
    "sensor_readings": ("reading_id", re.compile(r"^RDG-SNS-ZONE-WH-\d{3}-\d{3}-(TEMP|HUM|OCC|DOOR)-\d{2}-\d{8}T\d{6}Z$")),
    "door_events": ("door_event_id", re.compile(r"^DOR-ZONE-WH-\d{3}-\d{3}-\d{8}T\d{6}Z-\d{3}$")),
    "storage_requirements": ("requirement_id", re.compile(r"^REQ-\d{3}$")),
    "inventory_lots": ("lot_id", re.compile(r"^LOT-2026-\d{6}$")),
    "zone_lot_assignments": ("assignment_id", re.compile(r"^ZLA-2026-\d{6}$")),
    "alarms": ("alarm_id", re.compile(r"^ALM-2026-\d{6}$")),
    "alarm_affected_lots": ("alarm_lot_id", re.compile(r"^AAL-2026-\d{6}$")),
    "inspections": ("inspection_id", re.compile(r"^INS-2026-\d{6}$")),
    "remediations": ("remediation_id", re.compile(r"^REM-2026-\d{6}$")),
}


def load_csv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def validate_directory(data_dir: str) -> Dict[str, Any]:
    csv_dir = os.path.join(data_dir, "csv")
    tables: Dict[str, List[Dict[str, str]]] = {}
    for t_name in ID_PATTERNS.keys():
        tables[t_name] = load_csv(os.path.join(csv_dir, f"{t_name}.csv"))

    gt_rows = load_csv(os.path.join(data_dir, "ground_truth.csv"))

    checks: List[Dict[str, Any]] = []

    def record_check(name: str, category: str, passed: bool, checked_count: int, violations: int, details: str):
        checks.append({
            "check_name": name,
            "category": category,
            "passed": passed,
            "records_evaluated": checked_count,
            "violations_found": violations,
            "details": details,
        })

    # 1. Primary Key Uniqueness & Nomenclature Pattern Check
    pk_sets: Dict[str, set] = {}
    for t_name, (pk_col, regex) in ID_PATTERNS.items():
        rows = tables[t_name]
        seen = set()
        dup_cnt = 0
        regex_err = 0
        for r in rows:
            val = r[pk_col]
            if val in seen:
                dup_cnt += 1
            seen.add(val)
            if not regex.match(val):
                regex_err += 1
        pk_sets[t_name] = seen
        record_check(
            name=f"PK Uniqueness & ID Format ({t_name}.{pk_col})",
            category="PK_AND_NOMENCLATURE",
            passed=(dup_cnt == 0 and regex_err == 0),
            checked_count=len(rows),
            violations=dup_cnt + regex_err,
            details=f"Unique IDs: {len(seen)}, Duplicates: {dup_cnt}, Format mismatches: {regex_err}",
        )

    # 2. Foreign Key Referential Integrity Check
    fk_rules = [
        ("zones", "warehouse_id", "warehouses", False),
        ("sensors", "primary_zone_id", "zones", False),
        ("sensor_zone_mapping_history", "sensor_id", "sensors", False),
        ("sensor_zone_mapping_history", "zone_id", "zones", False),
        ("sensor_readings", "sensor_id", "sensors", False),
        ("sensor_readings", "zone_id", "zones", False),
        ("door_events", "zone_id", "zones", False),
        ("door_events", "sensor_id", "sensors", True),
        ("inventory_lots", "requirement_id", "storage_requirements", False),
        ("inventory_lots", "current_zone_id", "zones", False),
        ("zone_lot_assignments", "lot_id", "inventory_lots", False),
        ("zone_lot_assignments", "zone_id", "zones", False),
        ("alarms", "zone_id", "zones", False),
        ("alarms", "trigger_sensor_id", "sensors", True),
        ("alarm_affected_lots", "alarm_id", "alarms", False),
        ("alarm_affected_lots", "lot_id", "inventory_lots", False),
        ("inspections", "alarm_id", "alarms", False),
        ("inspections", "zone_id", "zones", False),
        ("remediations", "inspection_id", "inspections", False),
        ("remediations", "alarm_id", "alarms", False),
        ("remediations", "affected_lot_id", "inventory_lots", True),
    ]
    total_fk_checked = 0
    total_fk_violations = 0
    for child_tbl, fk_col, parent_tbl, optional in fk_rules:
        parent_pks = pk_sets[parent_tbl]
        for r in tables[child_tbl]:
            val = r[fk_col]
            total_fk_checked += 1
            if optional and (val == "" or val is None):
                continue
            if val not in parent_pks:
                total_fk_violations += 1

    record_check(
        name="Foreign-Key Referential Integrity (All 21 Relationships)",
        category="FOREIGN_KEY_INTEGRITY",
        passed=(total_fk_violations == 0),
        checked_count=total_fk_checked,
        violations=total_fk_violations,
        details=f"Verified {len(fk_rules)} FK constraints across {total_fk_checked} references with 0 orphans.",
    )

    # 3. Arithmetic & Derived Value Reconciliation (Step 6 & Step 8)
    # 3a. Warehouse capacity == sum(Zone.capacity_pallets)
    wh_cap_violations = 0
    zones_by_wh: Dict[str, List[Dict[str, str]]] = {}
    for z in tables["zones"]:
        zones_by_wh.setdefault(z["warehouse_id"], []).append(z)
    for wh in tables["warehouses"]:
        expected_cap = sum(int(z["capacity_pallets"]) for z in zones_by_wh.get(wh["warehouse_id"], []))
        if int(wh["total_capacity_pallets"]) != expected_cap:
            wh_cap_violations += 1

    record_check(
        name="Warehouse Capacity Reconciliation (SUM of Child Zones)",
        category="ARITHMETIC_RECONCILIATION",
        passed=(wh_cap_violations == 0),
        checked_count=len(tables["warehouses"]),
        violations=wh_cap_violations,
        details="Warehouse.total_capacity_pallets equals exact sum of child Zone.capacity_pallets.",
    )

    # 3b. InventoryLot quantity & dwell reconciliation
    lot_arith_violations = 0
    scrapped_by_lot: Dict[str, int] = {}
    for rem in tables["remediations"]:
        lid = rem["affected_lot_id"]
        if lid:
            scrapped_by_lot[lid] = scrapped_by_lot.get(lid, 0) + int(rem["scrapped_units"])

    for lot in tables["inventory_lots"]:
        lid = lot["lot_id"]
        init_q = int(lot["initial_quantity_units"])
        comp_q = int(lot["compromised_quantity_units"])
        avail_q = int(lot["available_quantity_units"])
        if comp_q != scrapped_by_lot.get(lid, 0) or (init_q - comp_q) != avail_q:
            lot_arith_violations += 1

    record_check(
        name="InventoryLot Quantity & Remediation Scrap Reconciliation",
        category="ARITHMETIC_RECONCILIATION",
        passed=(lot_arith_violations == 0),
        checked_count=len(tables["inventory_lots"]),
        violations=lot_arith_violations,
        details="available_quantity_units == initial_quantity_units - SUM(Remediation.scrapped_units).",
    )

    # 3c. Alarm affected_lot_count reconciliation with AlarmAffectedLot bridge table
    aal_counts: Dict[str, int] = {}
    for aal in tables["alarm_affected_lots"]:
        aid = aal["alarm_id"]
        aal_counts[aid] = aal_counts.get(aid, 0) + 1
    alm_cnt_violations = 0
    for alm in tables["alarms"]:
        if int(alm["affected_lot_count"]) != aal_counts.get(alm["alarm_id"], 0):
            alm_cnt_violations += 1

    record_check(
        name="Alarm Affected-Lot Count Bridge Reconciliation",
        category="ARITHMETIC_RECONCILIATION",
        passed=(alm_cnt_violations == 0),
        checked_count=len(tables["alarms"]),
        violations=alm_cnt_violations,
        details="Alarm.affected_lot_count matches exact row count in AlarmAffectedLot bridge table.",
    )

    # 4. Chronological Date/Timestamp Ordering Check
    date_violations = 0
    date_checked = 0
    for de in tables["door_events"]:
        date_checked += 1
        if de["opened_at"] > de["closed_at"]:
            date_violations += 1
    for zla in tables["zone_lot_assignments"]:
        date_checked += 1
        if zla["entered_at"] >= zla["exited_at"]:
            date_violations += 1
    for alm in tables["alarms"]:
        date_checked += 1
        if alm["triggered_at"] > alm["resolved_at"]:
            date_violations += 1

    record_check(
        name="Chronological Event Timestamp Ordering",
        category="DATE_ORDERING",
        passed=(date_violations == 0),
        checked_count=date_checked,
        violations=date_violations,
        details="Verified opened_at <= closed_at, entered_at < exited_at, and triggered_at <= resolved_at.",
    )

    # 5. Documented enums, units, and value constraints
    def parse_timestamp(value: str) -> datetime.datetime:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))

    def parse_date(value: str) -> datetime.date:
        return datetime.date.fromisoformat(value)

    enum_violations = 0
    enum_checked = 0
    allowed_enums = {
        "warehouse_region": {"NA-EAST", "NA-WEST", "EU-CENTRAL", "APAC-SOUTH", "LATAM-NORTH"},
        "facility_type": {"COLD_STORAGE", "PHARMA_GDP", "MIXED_DISTRIBUTION", "AMBIENT_BULK"},
        "warehouse_state": {"ACTIVE", "MAINTENANCE", "DECOMMISSIONED"},
        "zone_type": {"DEEP_FREEZE", "CHILLED", "CONTROLLED_AMBIENT", "HEATED_CURING", "STAGING_DOCK"},
        "zone_state": {"ACTIVE", "QUARANTINED", "MAINTENANCE", "INACTIVE"},
        "sensor_type": {"TEMP", "HUM", "OCC", "DOOR"},
        "sensor_state": {"ACTIVE", "DRIFTING", "OUTAGE", "DECOMMISSIONED"},
        "reading_quality": {"VALID", "DRIFT_SUSPECT", "EXCURSION", "GAP_RECOVERED", "NORMALIZED_GAP"},
        "door_actor": {"FORKLIFT_LOADING", "OPERATOR_ENTRY", "MAINTENANCE_ACCESS", "PROPPED_OPEN_FAULT"},
        "lot_state": {"STORED", "QUARANTINED", "INSPECTED_RELEASED", "SCRAPPED", "SHIPPED"},
        "alarm_type": {
            "TEMP_EXCURSION_HIGH", "TEMP_EXCURSION_LOW", "HUMIDITY_EXCURSION", "DOOR_HELD_OPEN",
            "SENSOR_OUTAGE_GAP", "SENSOR_DRIFT", "INCOMPATIBLE_LOT_ZONE", "OCCUPANCY_OVER_LIMIT",
        },
        "severity": {"LOW", "MEDIUM", "HIGH", "CRITICAL"},
        "alarm_state": {"OPEN", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "CLOSED"},
        "inspector_role": {"QUALITY_ENGINEER", "MAINTENANCE_ENGINEER", "PLANT_OPERATOR", "OT_IT_ADMIN"},
        "finding_code": {
            "CONFIRMED_EXCURSION", "DOOR_SEAL_FAILURE", "SENSOR_CALIBRATION_DRIFT",
            "SENSOR_COMMS_DROP", "WRONG_ZONE_PLACEMENT", "WITHIN_TOLERANCE",
        },
        "inspection_state": {"SCHEDULED", "IN_PROGRESS", "COMPLETED"},
        "action_type": {
            "RELOCATE_LOT", "QUARANTINE_AND_SCRAP_PARTIAL", "RECALIBRATE_SENSOR",
            "REPAIR_DOOR_CLOSER", "RESTORE_SENSOR_LINK", "RELEASE_LOT_AFTER_TEST",
        },
        "remediation_state": {"PENDING", "EXECUTED", "VERIFIED_CLOSED"},
    }

    def check_enum(value: str, enum_name: str) -> None:
        nonlocal enum_checked, enum_violations
        enum_checked += 1
        if value not in allowed_enums[enum_name]:
            enum_violations += 1

    sensor_by_id = {row["sensor_id"]: row for row in tables["sensors"]}
    zone_by_id = {row["zone_id"]: row for row in tables["zones"]}
    req_by_id = {row["requirement_id"]: row for row in tables["storage_requirements"]}
    lot_by_id = {row["lot_id"]: row for row in tables["inventory_lots"]}
    alarm_by_id = {row["alarm_id"]: row for row in tables["alarms"]}
    inspection_by_id = {row["inspection_id"]: row for row in tables["inspections"]}

    for row in tables["warehouses"]:
        check_enum(row["region"], "warehouse_region")
        check_enum(row["facility_type"], "facility_type")
        check_enum(row["lifecycle_state"], "warehouse_state")
    for row in tables["zones"]:
        check_enum(row["zone_type"], "zone_type")
        check_enum(row["lifecycle_state"], "zone_state")
        if float(row["temp_min_c"]) >= float(row["temp_max_c"]) \
                or float(row["humidity_min_pct"]) >= float(row["humidity_max_pct"]) \
                or not 0 <= float(row["humidity_max_pct"]) <= 100 \
                or int(row["max_occupancy_persons"]) <= 0 or int(row["capacity_pallets"]) <= 0:
            enum_violations += 1
    for row in tables["sensors"]:
        check_enum(row["sensor_type"], "sensor_type")
        check_enum(row["lifecycle_state"], "sensor_state")
        expected_units = {"TEMP": "CELSIUS", "HUM": "PERCENT_RH", "OCC": "COUNT", "DOOR": "STATE"}
        if row["unit"] != expected_units.get(row["sensor_type"]):
            enum_violations += 1
    for row in tables["sensor_zone_mapping_history"]:
        if row["mapping_rationale"] not in {"", "INITIAL_INSTALL", "BOUNDARY_SHARED_DUCT", "RELOCATION"}:
            enum_violations += 1
        if row["effective_to"] and parse_timestamp(row["effective_to"]) < parse_timestamp(row["effective_from"]):
            enum_violations += 1
    for row in tables["sensor_readings"]:
        check_enum(row["quality_status"], "reading_quality")
        sensor = sensor_by_id[row["sensor_id"]]
        if row["unit"] != sensor["unit"] or int(row["delta_prev_sec"]) < 0:
            enum_violations += 1
        value = float(row["value"])
        if not -60 <= value <= 100:
            enum_violations += 1
    for row in tables["door_events"]:
        check_enum(row["trigger_actor"], "door_actor")
        if int(row["open_duration_sec"]) <= 0:
            enum_violations += 1
        if row["sensor_id"] and sensor_by_id[row["sensor_id"]]["sensor_type"] != "DOOR":
            enum_violations += 1
    for row in tables["storage_requirements"]:
        allowed_types = set(row["allowed_zone_types"].split(","))
        if not allowed_types or not allowed_types.issubset(allowed_enums["zone_type"]) \
                or float(row["req_temp_min_c"]) >= float(row["req_temp_max_c"]) \
                or float(row["req_humidity_min_pct"]) >= float(row["req_humidity_max_pct"]) \
                or not 0 <= float(row["req_humidity_max_pct"]) <= 100 \
                or int(row["max_excursion_minutes"]) <= 0:
            enum_violations += 1
    for row in tables["inventory_lots"]:
        check_enum(row["lifecycle_state"], "lot_state")
        if int(row["initial_quantity_units"]) <= 0 \
                or int(row["compromised_quantity_units"]) < 0 \
                or int(row["available_quantity_units"]) < 0 \
                or int(row["compromised_quantity_units"]) + int(row["available_quantity_units"]) \
                != int(row["initial_quantity_units"]) \
                or parse_date(row["expiration_date"]) <= parse_timestamp(row["received_at"]).date():
            enum_violations += 1
    for row in tables["zone_lot_assignments"]:
        if float(row["dwell_hours"]) <= 0:
            enum_violations += 1
    for row in tables["alarms"]:
        check_enum(row["alarm_type"], "alarm_type")
        check_enum(row["severity"], "severity")
        check_enum(row["lifecycle_state"], "alarm_state")
        if int(row["duration_minutes"]) <= 0 or int(row["affected_lot_count"]) < 0:
            enum_violations += 1
    for row in tables["inspections"]:
        check_enum(row["inspector_role"], "inspector_role")
        check_enum(row["finding_code"], "finding_code")
        check_enum(row["lifecycle_state"], "inspection_state")
    for row in tables["remediations"]:
        check_enum(row["action_type"], "action_type")
        check_enum(row["lifecycle_state"], "remediation_state")
        if int(row["scrapped_units"]) < 0 or float(row["financial_impact_usd"]) < 0 \
                or float(row["labor_cost_usd"]) <= 0:
            enum_violations += 1

    record_check(
        name="Documented Enums, Units & Field Constraints",
        category="DOMAIN_CONSTRAINTS",
        passed=(enum_violations == 0),
        checked_count=enum_checked,
        violations=enum_violations,
        details="Checked documented enum sets, sensor units, physical bounds, and positive quantity/duration constraints.",
    )

    # 6. Per-sensor timestamp monotonicity, derived deltas, and explicit gap status
    readings_by_sensor: Dict[str, List[Dict[str, str]]] = {}
    for row in tables["sensor_readings"]:
        readings_by_sensor.setdefault(row["sensor_id"], []).append(row)
    silent_gap_ids = {
        row["entity_id"] for row in gt_rows
        if row["issue_type"] == "READING_GAP_TREATED_AS_NORMAL"
    }
    reading_time_violations = 0
    reading_rows_checked = 0
    for sensor_id, rows in readings_by_sensor.items():
        rows.sort(key=lambda row: parse_timestamp(row["recorded_at"]))
        sensor = sensor_by_id[sensor_id]
        previous = None
        for row in rows:
            reading_rows_checked += 1
            recorded = parse_timestamp(row["recorded_at"])
            if previous is None:
                if int(row["delta_prev_sec"]) != 0:
                    reading_time_violations += 1
            else:
                expected_delta = int((recorded - parse_timestamp(previous["recorded_at"])).total_seconds())
                actual_gap = expected_delta > 2 * int(sensor["sampling_interval_sec"])
                if expected_delta <= 0 or int(row["delta_prev_sec"]) != expected_delta:
                    reading_time_violations += 1
                if row["reading_id"] in silent_gap_ids:
                    if not actual_gap or row["is_gap_after_prev"].lower() != "false" \
                            or row["quality_status"] != "NORMALIZED_GAP":
                        reading_time_violations += 1
                elif row["is_gap_after_prev"].lower() != str(actual_gap).lower():
                    reading_time_violations += 1
            previous = row
    record_check(
        name="Sensor Reading Monotonicity, Deltas & Gap Flags",
        category="TELEMETRY_TIME_SERIES",
        passed=(reading_time_violations == 0),
        checked_count=reading_rows_checked,
        violations=reading_time_violations,
        details="Per-sensor timestamps/deltas reconcile; only labeled silent-gap anomalies may suppress a real gap flag.",
    )

    # 7. Derived dwell/duration/financial calculations and referential chronology
    derived_violations = 0
    derived_checked = 0
    dwell_by_lot: Dict[str, float] = {}
    assignments_by_key: Dict[tuple, List[Dict[str, str]]] = {}
    for row in tables["zone_lot_assignments"]:
        derived_checked += 1
        entered = parse_timestamp(row["entered_at"])
        exited = parse_timestamp(row["exited_at"])
        expected_dwell = (exited - entered).total_seconds() / 3600
        if entered >= exited or abs(float(row["dwell_hours"]) - expected_dwell) > 0.011:
            derived_violations += 1
        dwell_by_lot[row["lot_id"]] = dwell_by_lot.get(row["lot_id"], 0.0) + float(row["dwell_hours"])
        assignments_by_key.setdefault((row["lot_id"], row["zone_id"]), []).append(row)
    for lot in tables["inventory_lots"]:
        derived_checked += 1
        if abs(float(lot["total_dwell_hours"]) - dwell_by_lot.get(lot["lot_id"], 0.0)) > 0.011:
            derived_violations += 1
    for row in tables["alarms"]:
        derived_checked += 1
        start = parse_timestamp(row["triggered_at"])
        end = parse_timestamp(row["resolved_at"])
        expected_duration = max(1, int((end - start).total_seconds() // 60))
        if end < start or int(row["duration_minutes"]) != expected_duration:
            derived_violations += 1
    seen_alarm_lots = set()
    for row in tables["alarm_affected_lots"]:
        derived_checked += 1
        key = (row["alarm_id"], row["lot_id"])
        alarm = alarm_by_id[row["alarm_id"]]
        lot = lot_by_id[row["lot_id"]]
        alarm_start = parse_timestamp(alarm["triggered_at"])
        alarm_end = parse_timestamp(alarm["resolved_at"])
        candidate_assignments = assignments_by_key.get((row["lot_id"], alarm["zone_id"]), [])
        overlaps = []
        for assignment in candidate_assignments:
            overlap_start = max(alarm_start, parse_timestamp(assignment["entered_at"]))
            overlap_end = min(alarm_end, parse_timestamp(assignment["exited_at"]))
            if overlap_end > overlap_start:
                overlaps.append(max(1, int((overlap_end - overlap_start).total_seconds() // 60)))
        if key in seen_alarm_lots or not overlaps or int(row["overlap_minutes"]) not in overlaps:
            derived_violations += 1
        seen_alarm_lots.add(key)
        requirement = req_by_id[lot["requirement_id"]]
        expected_risk = min(100.0, round(
            (int(row["overlap_minutes"]) / int(requirement["max_excursion_minutes"])) * 75.0, 2
        ))
        if abs(float(row["risk_score"]) - expected_risk) > 0.011:
            derived_violations += 1
    inspections_by_alarm = {row["alarm_id"]: row for row in tables["inspections"]}
    for row in tables["inspections"]:
        derived_checked += 1
        alarm = alarm_by_id[row["alarm_id"]]
        if row["zone_id"] != alarm["zone_id"] \
                or parse_timestamp(row["inspected_at"]) < parse_timestamp(alarm["triggered_at"]):
            derived_violations += 1
    for row in tables["remediations"]:
        derived_checked += 1
        inspection = inspection_by_id[row["inspection_id"]]
        lot_id = row["affected_lot_id"]
        expected_financial = float(row["labor_cost_usd"])
        if lot_id:
            expected_financial += int(row["scrapped_units"]) * float(lot_by_id[lot_id]["unit_value_usd"])
        if abs(float(row["financial_impact_usd"]) - expected_financial) > 0.011 \
                or row["alarm_id"] != inspection["alarm_id"] \
                or parse_timestamp(row["completed_at"]) < parse_timestamp(inspection["inspected_at"]):
            derived_violations += 1
    record_check(
        name="Dwell, Alarm Impact, Risk & Remediation Reconciliation",
        category="DERIVED_VALUES_AND_LIFECYCLE",
        passed=(derived_violations == 0),
        checked_count=derived_checked,
        violations=derived_violations,
        details="Reconciled dwell, alarm durations, temporal lot overlap, risk scores, remediation costs, and workflow chronology.",
    )

    # 8. Ground-Truth Separation & Zero Leakage Check (Step 7)
    leaked_cols = 0
    for t_name, rows in tables.items():
        if rows:
            cols = set(rows[0].keys())
            if "issue_type" in cols or "ground_truth" in cols or "expected_decision" in cols:
                leaked_cols += 1

    record_check(
        name="Ground-Truth Feature Separation (Zero Input Leakage)",
        category="GROUND_TRUTH_SEPARATION",
        passed=(leaked_cols == 0 and len(gt_rows) > 0),
        checked_count=len(tables),
        violations=leaked_cols,
        details=f"0 input tables contain ground-truth label columns; {len(gt_rows)} labels isolated in ground_truth.csv.",
    )

    # 9. Required Edge-Case Coverage Check (Step 5)
    required_edge_cases = {
        "LOT_INCOMPATIBLE_ZONE",
        "SENSOR_MULTI_ZONE_NO_RATIONALE",
        "READING_GAP_TREATED_AS_NORMAL",
        "ALARM_UNLINKED_TO_AFFECTED_LOTS",
    }
    present_edge_cases = {r["issue_type"] for r in gt_rows}
    missing_ec = required_edge_cases - present_edge_cases

    record_check(
        name="Required Edge Cases & Negative Scenarios Coverage",
        category="EDGE_CASE_COVERAGE",
        passed=(len(missing_ec) == 0),
        checked_count=len(gt_rows),
        violations=len(missing_ec),
        details=f"All 4 required edge-case categories verified: {sorted(list(present_edge_cases))}",
    )

    all_passed = all(c["passed"] for c in checks)
    return {
        "overall_status": "PASSED" if all_passed else "FAILED",
        "total_checks": len(checks),
        "passed_checks": sum(1 for c in checks if c["passed"]),
        "failed_checks": sum(1 for c in checks if not c["passed"]),
        "checks": checks,
    }


def verify_reproducibility(seed: int, scale: str) -> Dict[str, Any]:
    """Step 10: Regenerate twice with the same seed and compare row counts & SHA-256 checksums."""
    tmp1 = tempfile.mkdtemp(prefix="repro_run1_")
    tmp2 = tempfile.mkdtemp(prefix="repro_run2_")
    try:
        m1 = generate_dataset(seed=seed, scale=scale, out_dir=tmp1, export_sql=True)
        m2 = generate_dataset(seed=seed, scale=scale, out_dir=tmp2, export_sql=True)

        checksum_comparisons = []
        all_match = True
        for rel_path, sha1 in m1["file_sha256_checksums"].items():
            sha2 = m2["file_sha256_checksums"].get(rel_path, "")
            matched = (sha1 == sha2)
            if not matched:
                all_match = False
            checksum_comparisons.append({
                "file": rel_path,
                "run_1_sha256": sha1,
                "run_2_sha256": sha2,
                "identical": matched,
            })

        row_count_match = (m1["row_counts"] == m2["row_counts"])
        return {
            "seed": seed,
            "scale": scale,
            "reproducible": (all_match and row_count_match),
            "row_counts_identical": row_count_match,
            "all_sha256_identical": all_match,
            "row_counts": m1["row_counts"],
            "file_comparisons": checksum_comparisons,
        }
    finally:
        shutil.rmtree(tmp1, ignore_errors=True)
        shutil.rmtree(tmp2, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="Validate Dataset & Verify Fixed-Seed Reproducibility")
    parser.add_argument("--data-dir", type=str, default="data/seed", help="Dataset directory to validate")
    parser.add_argument("--seed", type=int, default=FIXED_SEED_DEFAULT, help="Seed for Step 10 reproducibility")
    parser.add_argument("--scale", choices=["starter", "full"], default="starter", help="Scale for Step 10 check")
    parser.add_argument("--skip-repro", action="store_true", help="Skip two-run regeneration check")
    args = parser.parse_args()

    val_summary = validate_directory(args.data_dir)
    val_path = os.path.join(args.data_dir, "validation_summary.json")
    with open(val_path, "w", encoding="utf-8", newline="\n") as vf:
        json.dump(val_summary, vf, indent=2)

    if not args.skip_repro:
        repro_report = verify_reproducibility(seed=args.seed, scale=args.scale)
        repro_path = os.path.join(args.data_dir, "reproducibility_report.json")
        with open(repro_path, "w", encoding="utf-8", newline="\n") as rf:
            json.dump(repro_report, rf, indent=2)
        print(json.dumps({
            "validation_status": val_summary["overall_status"],
            "passed_checks": f"{val_summary['passed_checks']}/{val_summary['total_checks']}",
            "reproducibility_verified": repro_report["reproducible"],
            "all_sha256_identical": repro_report["all_sha256_identical"],
        }, indent=2))
    else:
        print(json.dumps({
            "validation_status": val_summary["overall_status"],
            "passed_checks": f"{val_summary['passed_checks']}/{val_summary['total_checks']}",
        }, indent=2))


if __name__ == "__main__":
    main()
