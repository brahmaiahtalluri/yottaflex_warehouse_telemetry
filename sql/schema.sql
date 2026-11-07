-- =============================================================================
-- Warehouse Zone Telemetry & Risk Alerting Platform — DDL Schema (SQL-99 / H2 / PostgreSQL)
-- Fixed Seed: 20261022
-- =============================================================================

DROP TABLE IF EXISTS remediation CASCADE;
DROP TABLE IF EXISTS inspection CASCADE;
DROP TABLE IF EXISTS alarm_affected_lot CASCADE;
DROP TABLE IF EXISTS alarm CASCADE;
DROP TABLE IF EXISTS zone_lot_assignment CASCADE;
DROP TABLE IF EXISTS inventory_lot CASCADE;
DROP TABLE IF EXISTS storage_requirement CASCADE;
DROP TABLE IF EXISTS door_event CASCADE;
DROP TABLE IF EXISTS sensor_reading CASCADE;
DROP TABLE IF EXISTS sensor_zone_mapping_history CASCADE;
DROP TABLE IF EXISTS sensor CASCADE;
DROP TABLE IF EXISTS warehouse_zone CASCADE;
DROP TABLE IF EXISTS warehouse CASCADE;

CREATE TABLE warehouse (
    warehouse_id VARCHAR(16) PRIMARY KEY,
    warehouse_name VARCHAR(100) NOT NULL UNIQUE,
    region VARCHAR(32) NOT NULL,
    facility_type VARCHAR(32) NOT NULL,
    total_capacity_pallets INTEGER NOT NULL CHECK (total_capacity_pallets > 0),
    active_zone_count INTEGER NOT NULL CHECK (active_zone_count >= 0),
    lifecycle_state VARCHAR(24) NOT NULL,
    effective_from TIMESTAMP NOT NULL,
    effective_to TIMESTAMP NULL
);

CREATE TABLE warehouse_zone (
    zone_id VARCHAR(32) PRIMARY KEY,
    warehouse_id VARCHAR(16) NOT NULL REFERENCES warehouse(warehouse_id),
    zone_name VARCHAR(100) NOT NULL,
    zone_type VARCHAR(24) NOT NULL,
    temp_min_c DECIMAL(6,2) NOT NULL,
    temp_max_c DECIMAL(6,2) NOT NULL,
    humidity_min_pct DECIMAL(5,2) NOT NULL,
    humidity_max_pct DECIMAL(5,2) NOT NULL,
    max_occupancy_persons INTEGER NOT NULL CHECK (max_occupancy_persons > 0),
    capacity_pallets INTEGER NOT NULL CHECK (capacity_pallets > 0),
    lifecycle_state VARCHAR(24) NOT NULL,
    effective_from TIMESTAMP NOT NULL,
    CHECK (temp_min_c < temp_max_c),
    CHECK (humidity_min_pct < humidity_max_pct)
);

CREATE TABLE sensor (
    sensor_id VARCHAR(48) PRIMARY KEY,
    primary_zone_id VARCHAR(32) NOT NULL REFERENCES warehouse_zone(zone_id),
    sensor_type VARCHAR(16) NOT NULL,
    unit VARCHAR(16) NOT NULL,
    sampling_interval_sec INTEGER NOT NULL CHECK (sampling_interval_sec > 0),
    drift_rate_per_day DECIMAL(6,4) NOT NULL,
    calibration_due_date DATE NOT NULL,
    lifecycle_state VARCHAR(24) NOT NULL,
    installed_at TIMESTAMP NOT NULL
);

CREATE TABLE sensor_zone_mapping_history (
    mapping_id VARCHAR(24) PRIMARY KEY,
    sensor_id VARCHAR(48) NOT NULL REFERENCES sensor(sensor_id),
    zone_id VARCHAR(32) NOT NULL REFERENCES warehouse_zone(zone_id),
    mapping_rationale VARCHAR(120) NULL,
    effective_from TIMESTAMP NOT NULL,
    effective_to TIMESTAMP NULL
);

CREATE TABLE sensor_reading (
    reading_id VARCHAR(80) PRIMARY KEY,
    sensor_id VARCHAR(48) NOT NULL REFERENCES sensor(sensor_id),
    zone_id VARCHAR(32) NOT NULL REFERENCES warehouse_zone(zone_id),
    recorded_at TIMESTAMP NOT NULL,
    value DECIMAL(8,3) NOT NULL,
    unit VARCHAR(16) NOT NULL,
    delta_prev_sec INTEGER NOT NULL CHECK (delta_prev_sec >= 0),
    is_excursion BOOLEAN NOT NULL,
    is_gap_after_prev BOOLEAN NOT NULL,
    quality_status VARCHAR(24) NOT NULL
);

CREATE TABLE door_event (
    door_event_id VARCHAR(64) PRIMARY KEY,
    zone_id VARCHAR(32) NOT NULL REFERENCES warehouse_zone(zone_id),
    sensor_id VARCHAR(48) NULL REFERENCES sensor(sensor_id),
    opened_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP NULL,
    open_duration_sec INTEGER NOT NULL CHECK (open_duration_sec > 0),
    trigger_actor VARCHAR(32) NOT NULL,
    caused_excursion BOOLEAN NOT NULL
);

CREATE TABLE storage_requirement (
    requirement_id VARCHAR(16) PRIMARY KEY,
    product_category VARCHAR(64) NOT NULL UNIQUE,
    req_temp_min_c DECIMAL(6,2) NOT NULL,
    req_temp_max_c DECIMAL(6,2) NOT NULL,
    req_humidity_min_pct DECIMAL(5,2) NOT NULL,
    req_humidity_max_pct DECIMAL(5,2) NOT NULL,
    max_excursion_minutes INTEGER NOT NULL CHECK (max_excursion_minutes > 0),
    allowed_zone_types VARCHAR(100) NOT NULL
);

CREATE TABLE inventory_lot (
    lot_id VARCHAR(24) PRIMARY KEY,
    requirement_id VARCHAR(16) NOT NULL REFERENCES storage_requirement(requirement_id),
    current_zone_id VARCHAR(32) NOT NULL REFERENCES warehouse_zone(zone_id),
    product_sku VARCHAR(32) NOT NULL,
    initial_quantity_units INTEGER NOT NULL CHECK (initial_quantity_units > 0),
    compromised_quantity_units INTEGER NOT NULL CHECK (compromised_quantity_units >= 0),
    available_quantity_units INTEGER NOT NULL CHECK (available_quantity_units >= 0),
    unit_value_usd DECIMAL(10,2) NOT NULL CHECK (unit_value_usd > 0),
    total_dwell_hours DECIMAL(8,2) NOT NULL CHECK (total_dwell_hours >= 0),
    cumulative_excursion_min INTEGER NOT NULL CHECK (cumulative_excursion_min >= 0),
    lifecycle_state VARCHAR(24) NOT NULL,
    received_at TIMESTAMP NOT NULL,
    expiration_date DATE NOT NULL
);

CREATE TABLE zone_lot_assignment (
    assignment_id VARCHAR(24) PRIMARY KEY,
    lot_id VARCHAR(24) NOT NULL REFERENCES inventory_lot(lot_id),
    zone_id VARCHAR(32) NOT NULL REFERENCES warehouse_zone(zone_id),
    entered_at TIMESTAMP NOT NULL,
    exited_at TIMESTAMP NULL,
    dwell_hours DECIMAL(8,2) NOT NULL CHECK (dwell_hours >= 0),
    is_zone_compatible BOOLEAN NOT NULL
);

CREATE TABLE alarm (
    alarm_id VARCHAR(24) PRIMARY KEY,
    zone_id VARCHAR(32) NOT NULL REFERENCES warehouse_zone(zone_id),
    trigger_sensor_id VARCHAR(48) NULL REFERENCES sensor(sensor_id),
    alarm_type VARCHAR(32) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    triggered_at TIMESTAMP NOT NULL,
    resolved_at TIMESTAMP NULL,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
    peak_value DECIMAL(8,3) NOT NULL,
    threshold_limit DECIMAL(8,3) NOT NULL,
    affected_lot_count INTEGER NOT NULL CHECK (affected_lot_count >= 0),
    lifecycle_state VARCHAR(24) NOT NULL
);

CREATE TABLE alarm_affected_lot (
    alarm_lot_id VARCHAR(24) PRIMARY KEY,
    alarm_id VARCHAR(24) NOT NULL REFERENCES alarm(alarm_id),
    lot_id VARCHAR(24) NOT NULL REFERENCES inventory_lot(lot_id),
    overlap_minutes INTEGER NOT NULL CHECK (overlap_minutes > 0),
    risk_score DECIMAL(5,2) NOT NULL
);

CREATE TABLE inspection (
    inspection_id VARCHAR(24) PRIMARY KEY,
    alarm_id VARCHAR(24) NOT NULL REFERENCES alarm(alarm_id),
    zone_id VARCHAR(32) NOT NULL REFERENCES warehouse_zone(zone_id),
    inspector_role VARCHAR(32) NOT NULL,
    inspected_at TIMESTAMP NOT NULL,
    finding_code VARCHAR(32) NOT NULL,
    requires_remediation BOOLEAN NOT NULL,
    lifecycle_state VARCHAR(24) NOT NULL
);

CREATE TABLE remediation (
    remediation_id VARCHAR(24) PRIMARY KEY,
    inspection_id VARCHAR(24) NOT NULL REFERENCES inspection(inspection_id),
    alarm_id VARCHAR(24) NOT NULL REFERENCES alarm(alarm_id),
    affected_lot_id VARCHAR(24) NULL REFERENCES inventory_lot(lot_id),
    action_type VARCHAR(32) NOT NULL,
    scrapped_units INTEGER NOT NULL CHECK (scrapped_units >= 0),
    financial_impact_usd DECIMAL(12,2) NOT NULL CHECK (financial_impact_usd >= 0),
    labor_cost_usd DECIMAL(10,2) NOT NULL CHECK (labor_cost_usd >= 0),
    completed_at TIMESTAMP NOT NULL,
    lifecycle_state VARCHAR(24) NOT NULL
);

CREATE INDEX idx_zone_wh ON warehouse_zone(warehouse_id);
CREATE INDEX idx_sensor_zone ON sensor(primary_zone_id);
CREATE INDEX idx_reading_sensor_time ON sensor_reading(sensor_id, recorded_at);
CREATE INDEX idx_reading_zone_time ON sensor_reading(zone_id, recorded_at);
CREATE INDEX idx_lot_zone ON inventory_lot(current_zone_id);
CREATE INDEX idx_zla_zone_time ON zone_lot_assignment(zone_id, entered_at, exited_at);
CREATE INDEX idx_alarm_zone_time ON alarm(zone_id, triggered_at, resolved_at);
