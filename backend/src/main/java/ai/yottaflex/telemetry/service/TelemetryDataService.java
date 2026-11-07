package ai.yottaflex.telemetry.service;

import ai.yottaflex.telemetry.TelemetryProperties;
import ai.yottaflex.telemetry.model.DomainModels.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.stream.Collectors;
import java.nio.file.StandardOpenOption;

@Service
public class TelemetryDataService {

    private String configuredDataDir = "../data/seed";
    private String configuredWorkflowJournalPath = "data/runtime/workflow-events.jsonl";

    private final ObjectMapper objectMapper;
    private final TelemetryProperties telemetryProperties;

    private final List<Warehouse> warehouses = new CopyOnWriteArrayList<>();
    private final List<Zone> zones = new CopyOnWriteArrayList<>();
    private final List<Sensor> sensors = new CopyOnWriteArrayList<>();
    private final List<SensorZoneMapping> sensorMappings = new CopyOnWriteArrayList<>();
    private final List<SensorReading> sensorReadings = new CopyOnWriteArrayList<>();
    private final List<DoorEvent> doorEvents = new CopyOnWriteArrayList<>();
    private final List<StorageRequirement> storageRequirements = new CopyOnWriteArrayList<>();
    private final List<InventoryLot> inventoryLots = new CopyOnWriteArrayList<>();
    private final List<ZoneLotAssignment> zoneLotAssignments = new CopyOnWriteArrayList<>();
    private final List<Alarm> alarms = new CopyOnWriteArrayList<>();
    private final List<AlarmAffectedLot> alarmAffectedLots = new CopyOnWriteArrayList<>();
    private final List<Inspection> inspections = new CopyOnWriteArrayList<>();
    private final List<Remediation> remediations = new CopyOnWriteArrayList<>();
    private final List<GroundTruthItem> groundTruthItems = new CopyOnWriteArrayList<>();
    private final List<Map<String, Object>> auditEventLog = new CopyOnWriteArrayList<>();

    public TelemetryDataService(ObjectMapper objectMapper) {
        this(objectMapper, new TelemetryProperties());
    }

    @Autowired
    public TelemetryDataService(ObjectMapper objectMapper, TelemetryProperties telemetryProperties) {
        this.objectMapper = objectMapper;
        this.telemetryProperties = telemetryProperties;
        this.configuredDataDir = telemetryProperties.getDataDir();
        this.configuredWorkflowJournalPath = telemetryProperties.getWorkflowJournal();
    }

    @PostConstruct
    public void init() {
        Path baseDir = resolveDataDir();
        Path csvDir = baseDir.resolve("csv");
        try {
            loadAllTables(baseDir, csvDir);
            loadWorkflowJournal(resolveWorkflowJournalPath(baseDir));
        } catch (IOException e) {
            throw new IllegalStateException("Failed to load telemetry data or workflow journal from " + baseDir, e);
        }
    }

    // private Path resolveDataDir() {
    //     List<Path> candidates = List.of(
    //             Paths.get(configuredDataDir),
    //             Paths.get("data/seed"),
    //             Paths.get("../data/seed")
    //     );
    //     for (Path p : candidates) {
    //         if (Files.exists(p.resolve("csv/warehouses.csv"))) {
    //             return p.toAbsolutePath().normalize();
    //         }
    //     }
    //     return Paths.get(configuredDataDir).toAbsolutePath().normalize();
    // }
    private Path resolveDataDir() {
        List<Path> candidates = new ArrayList<>();
        if (configuredDataDir != null && !configuredDataDir.trim().isEmpty()) {
            candidates.add(Paths.get(configuredDataDir));
            candidates.add(Paths.get("..", configuredDataDir));
        }
        candidates.add(Paths.get("..", "data", "seed"));
        candidates.add(Paths.get("data", "seed"));
        candidates.add(Paths.get("..", "data"));
        candidates.add(Paths.get("data"));

        for (Path p : candidates) {
            Path candidateCsv = p.resolve("csv").resolve("warehouses.csv").normalize();
            if (Files.exists(candidateCsv)) {
                System.out.println(">>> [TelemetryDataService] Successfully resolved seed data dir: " + p.toAbsolutePath().normalize());
                return p.toAbsolutePath().normalize();
            }
        }

        // Direct absolute path fallback if relative resolution fails
        Path fallback = Paths.get("..", "data", "seed").toAbsolutePath().normalize();
        System.err.println(">>> [TelemetryDataService] WARNING: Could not find warehouses.csv in candidates, falling back to: " + fallback);
        return fallback;
    }

    private Path resolveWorkflowJournalPath(Path baseDir) {
        Path configuredPath = Paths.get(configuredWorkflowJournalPath);
        if (configuredPath.isAbsolute()) {
            return configuredPath.normalize();
        }
        Path projectRoot = baseDir.getParent() == null || baseDir.getParent().getParent() == null
                ? Paths.get("").toAbsolutePath()
                : baseDir.getParent().getParent();
        return projectRoot.resolve(configuredPath).normalize();
    }

    private void loadWorkflowJournal(Path journalPath) throws IOException {
        if (!Files.exists(journalPath)) {
            return;
        }
        int lineNumber = 0;
        for (String line : Files.readAllLines(journalPath, StandardCharsets.UTF_8)) {
            lineNumber++;
            if (line.isBlank()) {
                continue;
            }
            WorkflowEvent event;
            try {
                event = objectMapper.readValue(line, WorkflowEvent.class);
            } catch (IOException e) {
                throw new IOException("Invalid workflow journal entry at " + journalPath + ":" + lineNumber, e);
            }
            if (event.inspection() == null || event.remediation() == null || event.eventId() == null) {
                throw new IOException("Incomplete workflow journal entry at " + journalPath + ":" + lineNumber);
            }
            inspections.add(event.inspection());
            remediations.add(event.remediation());
            if (event.updatedLot() != null) {
                replaceLot(event.updatedLot());
            }
            if (event.newAssignment() != null) {
                zoneLotAssignments.add(event.newAssignment());
            }
            auditEventLog.add(toAuditEvent(event));
        }
    }

    private void appendWorkflowEvent(Path journalPath, WorkflowEvent event) throws IOException {
        Files.createDirectories(journalPath.getParent());
        String serializedEvent = objectMapper.writeValueAsString(event) + System.lineSeparator();
        Files.writeString(
                journalPath,
                serializedEvent,
                StandardCharsets.UTF_8,
                StandardOpenOption.CREATE,
                StandardOpenOption.WRITE,
                StandardOpenOption.APPEND
        );
    }

    private Map<String, Object> toAuditEvent(WorkflowEvent event) {
        Map<String, Object> auditEvent = new LinkedHashMap<>();
        auditEvent.put("event_id", event.eventId());
        auditEvent.put("timestamp", event.timestamp());
        auditEvent.put("actor_role", event.actorRole());
        auditEvent.put("alarm_id", event.alarmId());
        auditEvent.put("inspection_id", event.inspection().inspectionId());
        auditEvent.put("remediation_id", event.remediation().remediationId());
        auditEvent.put("affected_lot_id", event.remediation().affectedLotId());
        auditEvent.put("financial_impact_usd", event.remediation().financialImpactUsd());
        return auditEvent;
    }

    private void replaceLot(InventoryLot updatedLot) {
        for (int i = 0; i < inventoryLots.size(); i++) {
            if (inventoryLots.get(i).lotId().equals(updatedLot.lotId())) {
                inventoryLots.set(i, updatedLot);
                return;
            }
        }
        throw new IllegalStateException("Workflow journal references unknown lot: " + updatedLot.lotId());
    }

    private void loadAllTables(Path baseDir, Path csvDir) throws IOException {
        warehouses.clear();
        for (Map<String, String> r : readCsv(csvDir.resolve("warehouses.csv"))) {
            warehouses.add(new Warehouse(
                    r.get("warehouse_id"), r.get("warehouse_name"), r.get("region"),
                    r.get("facility_type"), Integer.parseInt(r.get("total_capacity_pallets")),
                    Integer.parseInt(r.get("active_zone_count")), r.get("lifecycle_state"),
                    r.get("effective_from"), r.getOrDefault("effective_to", "")
            ));
        }

        zones.clear();
        for (Map<String, String> r : readCsv(csvDir.resolve("zones.csv"))) {
            zones.add(new Zone(
                    r.get("zone_id"), r.get("warehouse_id"), r.get("zone_name"),
                    r.get("zone_type"), Double.parseDouble(r.get("temp_min_c")),
                    Double.parseDouble(r.get("temp_max_c")), Double.parseDouble(r.get("humidity_min_pct")),
                    Double.parseDouble(r.get("humidity_max_pct")), Integer.parseInt(r.get("max_occupancy_persons")),
                    Integer.parseInt(r.get("capacity_pallets")), r.get("lifecycle_state"),
                    r.get("effective_from")
            ));
        }

        sensors.clear();
        for (Map<String, String> r : readCsv(csvDir.resolve("sensors.csv"))) {
            sensors.add(new Sensor(
                    r.get("sensor_id"), r.get("primary_zone_id"), r.get("sensor_type"),
                    r.get("unit"), Integer.parseInt(r.get("sampling_interval_sec")),
                    Double.parseDouble(r.get("drift_rate_per_day")), r.get("calibration_due_date"),
                    r.get("lifecycle_state"), r.get("installed_at")
            ));
        }

        sensorMappings.clear();
        for (Map<String, String> r : readCsv(csvDir.resolve("sensor_zone_mapping_history.csv"))) {
            sensorMappings.add(new SensorZoneMapping(
                    r.get("mapping_id"), r.get("sensor_id"), r.get("zone_id"),
                    r.getOrDefault("mapping_rationale", ""), r.get("effective_from"),
                    r.getOrDefault("effective_to", "")
            ));
        }

        sensorReadings.clear();
        for (Map<String, String> r : readCsv(csvDir.resolve("sensor_readings.csv"))) {
            sensorReadings.add(new SensorReading(
                    r.get("reading_id"), r.get("sensor_id"), r.get("zone_id"),
                    r.get("recorded_at"), Double.parseDouble(r.get("value")),
                    r.get("unit"), Integer.parseInt(r.get("delta_prev_sec")),
                    Boolean.parseBoolean(r.get("is_excursion")),
                    Boolean.parseBoolean(r.get("is_gap_after_prev")),
                    r.get("quality_status")
            ));
        }

        doorEvents.clear();
        for (Map<String, String> r : readCsv(csvDir.resolve("door_events.csv"))) {
            doorEvents.add(new DoorEvent(
                    r.get("door_event_id"), r.get("zone_id"), r.get("sensor_id"),
                    r.get("opened_at"), r.get("closed_at"),
                    Integer.parseInt(r.get("open_duration_sec")),
                    r.get("trigger_actor"), Boolean.parseBoolean(r.get("caused_excursion"))
            ));
        }

        storageRequirements.clear();
        for (Map<String, String> r : readCsv(csvDir.resolve("storage_requirements.csv"))) {
            storageRequirements.add(new StorageRequirement(
                    r.get("requirement_id"), r.get("product_category"),
                    Double.parseDouble(r.get("req_temp_min_c")), Double.parseDouble(r.get("req_temp_max_c")),
                    Double.parseDouble(r.get("req_humidity_min_pct")), Double.parseDouble(r.get("req_humidity_max_pct")),
                    Integer.parseInt(r.get("max_excursion_minutes")), r.get("allowed_zone_types")
            ));
        }

        inventoryLots.clear();
        for (Map<String, String> r : readCsv(csvDir.resolve("inventory_lots.csv"))) {
            inventoryLots.add(new InventoryLot(
                    r.get("lot_id"), r.get("requirement_id"), r.get("current_zone_id"),
                    r.get("product_sku"), Integer.parseInt(r.get("initial_quantity_units")),
                    Integer.parseInt(r.get("compromised_quantity_units")),
                    Integer.parseInt(r.get("available_quantity_units")),
                    Double.parseDouble(r.get("unit_value_usd")),
                    Double.parseDouble(r.get("total_dwell_hours")),
                    Integer.parseInt(r.get("cumulative_excursion_min")),
                    r.get("lifecycle_state"), r.get("received_at"), r.get("expiration_date")
            ));
        }

        zoneLotAssignments.clear();
        for (Map<String, String> r : readCsv(csvDir.resolve("zone_lot_assignments.csv"))) {
            zoneLotAssignments.add(new ZoneLotAssignment(
                    r.get("assignment_id"), r.get("lot_id"), r.get("zone_id"),
                    r.get("entered_at"), r.get("exited_at"),
                    Double.parseDouble(r.get("dwell_hours")),
                    Boolean.parseBoolean(r.get("is_zone_compatible"))
            ));
        }

        alarms.clear();
        for (Map<String, String> r : readCsv(csvDir.resolve("alarms.csv"))) {
            alarms.add(new Alarm(
                    r.get("alarm_id"), r.get("zone_id"), r.get("trigger_sensor_id"),
                    r.get("alarm_type"), r.get("severity"), r.get("triggered_at"),
                    r.get("resolved_at"), Integer.parseInt(r.get("duration_minutes")),
                    Double.parseDouble(r.get("peak_value")), Double.parseDouble(r.get("threshold_limit")),
                    Integer.parseInt(r.get("affected_lot_count")), r.get("lifecycle_state")
            ));
        }

        alarmAffectedLots.clear();
        for (Map<String, String> r : readCsv(csvDir.resolve("alarm_affected_lots.csv"))) {
            alarmAffectedLots.add(new AlarmAffectedLot(
                    r.get("alarm_lot_id"), r.get("alarm_id"), r.get("lot_id"),
                    Integer.parseInt(r.get("overlap_minutes")), Double.parseDouble(r.get("risk_score"))
            ));
        }

        inspections.clear();
        for (Map<String, String> r : readCsv(csvDir.resolve("inspections.csv"))) {
            inspections.add(new Inspection(
                    r.get("inspection_id"), r.get("alarm_id"), r.get("zone_id"),
                    r.get("inspector_role"), r.get("inspected_at"), r.get("finding_code"),
                    Boolean.parseBoolean(r.get("requires_remediation")), r.get("lifecycle_state")
            ));
        }

        remediations.clear();
        for (Map<String, String> r : readCsv(csvDir.resolve("remediations.csv"))) {
            remediations.add(new Remediation(
                    r.get("remediation_id"), r.get("inspection_id"), r.get("alarm_id"),
                    r.getOrDefault("affected_lot_id", ""), r.get("action_type"),
                    Integer.parseInt(r.get("scrapped_units")),
                    Double.parseDouble(r.get("financial_impact_usd")),
                    Double.parseDouble(r.get("labor_cost_usd")),
                    r.get("completed_at"), r.get("lifecycle_state")
            ));
        }

        groundTruthItems.clear();
        Path gtPath = baseDir.resolve("ground_truth.csv");
        if (Files.exists(gtPath)) {
            for (Map<String, String> r : readCsv(gtPath)) {
                groundTruthItems.add(new GroundTruthItem(
                        r.get("ground_truth_id"), r.get("issue_type"), r.get("entity_type"),
                        r.get("entity_id"), r.get("zone_id"), r.get("related_entity_id"),
                        r.get("expected_decision"), r.get("severity"), r.get("detected_at"),
                        r.get("description")
                ));
            }
        }
    }

    private List<Map<String, String>> readCsv(Path path) throws IOException {
        List<Map<String, String>> rows = new ArrayList<>();
        try (BufferedReader br = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            String headerLine = br.readLine();
            if (headerLine == null) return rows;
            String[] headers = parseCsvLine(headerLine);
            String line;
            while ((line = br.readLine()) != null) {
                if (line.isBlank()) continue;
                String[] vals = parseCsvLine(line);
                Map<String, String> row = new LinkedHashMap<>();
                for (int i = 0; i < headers.length; i++) {
                    row.put(headers[i], i < vals.length ? vals[i] : "");
                }
                rows.add(row);
            }
        }
        return rows;
    }

    private String[] parseCsvLine(String line) {
        List<String> tokens = new ArrayList<>();
        StringBuilder sb = new StringBuilder();
        boolean inQuotes = false;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (c == '"') {
                inQuotes = !inQuotes;
            } else if (c == ',' && !inQuotes) {
                tokens.add(sb.toString());
                sb.setLength(0);
            } else {
                sb.append(c);
            }
        }
        tokens.add(sb.toString());
        return tokens.toArray(new String[0]);
    }

    public List<Warehouse> getWarehouses() { return warehouses; }
    public List<Zone> getZones() { return zones; }
    public List<Sensor> getSensors() { return sensors; }
    public List<SensorZoneMapping> getSensorMappings() { return sensorMappings; }
    public List<SensorReading> getSensorReadings() { return sensorReadings; }
    public List<DoorEvent> getDoorEvents() { return doorEvents; }
    public List<StorageRequirement> getStorageRequirements() { return storageRequirements; }
    public List<InventoryLot> getInventoryLots() { return inventoryLots; }
    public List<ZoneLotAssignment> getZoneLotAssignments() { return zoneLotAssignments; }
    public List<Alarm> getAlarms() { return alarms; }
    public List<AlarmAffectedLot> getAlarmAffectedLots() { return alarmAffectedLots; }
    public List<Inspection> getInspections() { return inspections; }
    public List<Remediation> getRemediations() { return remediations; }
    public List<GroundTruthItem> getGroundTruthItems() { return groundTruthItems; }
    public List<Map<String, Object>> getAuditEventLog() { return auditEventLog; }

    /**
     * Evaluates all 4 Required Negative Scenarios / Edge Cases purely from Input Tables
     * (never reading ground_truth during detection) and then benchmarks against ground_truth.csv.
     */
    public Map<String, Object> evaluateEdgeCasesAndGroundTruth() {
        List<DetectedException> detected = new ArrayList<>();
        Set<String> gtKeys = groundTruthItems.stream()
                .map(gt -> gt.issueType() + "::" + gt.entityId())
                .collect(Collectors.toSet());

        Map<String, Zone> zoneMap = zones.stream().collect(Collectors.toMap(Zone::zoneId, z -> z));
        Map<String, StorageRequirement> reqMap = storageRequirements.stream()
                .collect(Collectors.toMap(StorageRequirement::requirementId, r -> r));
        Map<String, Sensor> sensorMap = sensors.stream().collect(Collectors.toMap(Sensor::sensorId, s -> s));

        // Rule 1: LOT_INCOMPATIBLE_ZONE
        Map<String, ZoneLotAssignment> zlaByLot = zoneLotAssignments.stream()
                .collect(Collectors.toMap(ZoneLotAssignment::lotId, z -> z, (a, b) -> a));
        for (InventoryLot lot : inventoryLots) {
            Zone z = zoneMap.get(lot.currentZoneId());
            StorageRequirement req = reqMap.get(lot.requirementId());
            if (z != null && req != null) {
                List<String> allowed = Arrays.asList(req.allowedZoneTypes().split(","));
                if (!allowed.contains(z.zoneType())) {
                    ZoneLotAssignment zla = zlaByLot.get(lot.lotId());
                    String relId = zla != null ? zla.assignmentId() : "";
                    boolean match = gtKeys.contains("LOT_INCOMPATIBLE_ZONE::" + lot.lotId());
                    detected.add(new DetectedException(
                            "LOT_INCOMPATIBLE_ZONE", "InventoryLot", lot.lotId(), z.zoneId(),
                            relId, "REJECT_ASSIGNMENT_QUARANTINE_LOT", "CRITICAL",
                            String.format("Lot %s (%s) requires [%s] but is stored in %s (%s).",
                                    lot.lotId(), req.productCategory(), req.allowedZoneTypes(), z.zoneId(), z.zoneType()),
                            match
                    ));
                }
            }
        }

        // Rule 2: SENSOR_MULTI_ZONE_NO_RATIONALE
        Map<String, List<SensorZoneMapping>> mappingsBySensor = sensorMappings.stream()
                .collect(Collectors.groupingBy(SensorZoneMapping::sensorId));
        for (Map.Entry<String, List<SensorZoneMapping>> entry : mappingsBySensor.entrySet()) {
            if (entry.getValue().size() > 1) {
                for (SensorZoneMapping m : entry.getValue()) {
                    if (m.mappingRationale() == null || m.mappingRationale().isBlank()) {
                        boolean match = gtKeys.contains("SENSOR_MULTI_ZONE_NO_RATIONALE::" + entry.getKey());
                        detected.add(new DetectedException(
                                "SENSOR_MULTI_ZONE_NO_RATIONALE", "Sensor", entry.getKey(), m.zoneId(),
                                m.mappingId(), "FLAG_INVALID_TOPOLOGY_AUDIT", "HIGH",
                                String.format("Sensor %s has concurrent zone mapping %s without rationale.",
                                        entry.getKey(), m.mappingId()),
                                match
                        ));
                    }
                }
            }
        }

        // Rule 3: READING_GAP_TREATED_AS_NORMAL
        for (SensorReading rdg : sensorReadings) {
            Sensor s = sensorMap.get(rdg.sensorId());
            if (s != null && rdg.deltaPrevSec() > 2 * s.samplingIntervalSec() && !rdg.isGapAfterPrev()) {
                boolean match = gtKeys.contains("READING_GAP_TREATED_AS_NORMAL::" + rdg.readingId());
                detected.add(new DetectedException(
                        "READING_GAP_TREATED_AS_NORMAL", "SensorReading", rdg.readingId(), rdg.zoneId(),
                        rdg.sensorId(), "RAISE_MISSING_TELEMETRY_GAP_ALARM", "HIGH",
                        String.format("Reading %s had %ds gap (expected %ds) but is_gap_after_prev=false.",
                                rdg.readingId(), rdg.deltaPrevSec(), s.samplingIntervalSec()),
                        match
                ));
            }
        }

        // Rule 4: ALARM_UNLINKED_TO_AFFECTED_LOTS
        Map<String, List<ZoneLotAssignment>> zlasByZone = zoneLotAssignments.stream()
                .collect(Collectors.groupingBy(ZoneLotAssignment::zoneId));
        for (Alarm alm : alarms) {
            if (alm.affectedLotCount() == 0) {
                List<ZoneLotAssignment> zoneZlas = zlasByZone.getOrDefault(alm.zoneId(), List.of());
                Instant alarmStart = Instant.parse(alm.triggeredAt());
                Instant alarmEnd = Instant.parse(alm.resolvedAt());
                List<ZoneLotAssignment> overlapping = zoneZlas.stream()
                        .filter(zla -> Instant.parse(zla.enteredAt()).isBefore(alarmEnd)
                                && (zla.exitedAt().isBlank() || Instant.parse(zla.exitedAt()).isAfter(alarmStart)))
                        .toList();
                if (!overlapping.isEmpty()) {
                    String firstLot = overlapping.get(0).lotId();
                    boolean match = gtKeys.contains("ALARM_UNLINKED_TO_AFFECTED_LOTS::" + alm.alarmId());
                    detected.add(new DetectedException(
                            "ALARM_UNLINKED_TO_AFFECTED_LOTS", "Alarm", alm.alarmId(), alm.zoneId(),
                            firstLot, "BACKFILL_AFFECTED_LOT_LINKS_AND_QUARANTINE", "CRITICAL",
                            String.format("Alarm %s overlapped %d active lot(s) in %s but has 0 linked AlarmAffectedLot rows.",
                                    alm.alarmId(), overlapping.size(), alm.zoneId()),
                            match
                    ));
                }
            }
        }

        long truePositives = detected.stream().filter(DetectedException::matchesGroundTruth).count();
        int totalGroundTruth = groundTruthItems.size();
        double precision = detected.isEmpty() ? 1.0 : (double) truePositives / detected.size();
        double recall = totalGroundTruth == 0 ? 1.0 : (double) truePositives / totalGroundTruth;
        double f1 = (precision + recall) == 0 ? 0.0 : 2 * (precision * recall) / (precision + recall);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("totalDetectedExceptions", detected.size());
        result.put("totalGroundTruthLabels", totalGroundTruth);
        result.put("truePositives", truePositives);
        result.put("precisionPct", Math.round(precision * 10000.0) / 100.0);
        result.put("recallPct", Math.round(recall * 10000.0) / 100.0);
        result.put("f1ScorePct", Math.round(f1 * 10000.0) / 100.0);
        result.put("detectedExceptions", detected);
        result.put("groundTruthItems", groundTruthItems);
        return result;
    }

    /**
     * Builds full traceability view for a specific InventoryLot.
     */
    public Optional<LotTraceabilityView> getLotTraceability(String lotId) {
        Optional<InventoryLot> lotOpt = inventoryLots.stream().filter(l -> l.lotId().equals(lotId)).findFirst();
        if (lotOpt.isEmpty()) return Optional.empty();
        InventoryLot lot = lotOpt.get();

        StorageRequirement req = storageRequirements.stream()
                .filter(r -> r.requirementId().equals(lot.requirementId())).findFirst().orElse(null);
        Zone zone = zones.stream()
                .filter(z -> z.zoneId().equals(lot.currentZoneId())).findFirst().orElse(null);
        List<ZoneLotAssignment> lotZlas = zoneLotAssignments.stream()
                .filter(z -> z.lotId().equals(lotId)).toList();
        List<AlarmAffectedLot> aalLinks = alarmAffectedLots.stream()
                .filter(a -> a.lotId().equals(lotId)).toList();
        Set<String> alarmIds = aalLinks.stream().map(AlarmAffectedLot::alarmId).collect(Collectors.toSet());
        List<Alarm> lotAlarms = alarms.stream().filter(a -> alarmIds.contains(a.alarmId())).toList();
        List<Inspection> lotInspections = inspections.stream().filter(i -> alarmIds.contains(i.alarmId())).toList();
        List<Remediation> lotRemediations = remediations.stream()
                .filter(r -> lotId.equals(r.affectedLotId()) || alarmIds.contains(r.alarmId())).toList();

        boolean compat = lotZlas.stream().allMatch(ZoneLotAssignment::isZoneCompatible);
        double finRisk = Math.round(lot.compromisedQuantityUnits() * lot.unitValueUsd() * 100.0) / 100.0;

        return Optional.of(new LotTraceabilityView(
                lot, req, zone, lotZlas, lotAlarms, aalLinks, lotInspections, lotRemediations, compat, finRisk
        ));
    }

    /**
     * Appends an explicit Inspection + Remediation record without overwriting history (Rule 4).
     */
    public Map<String, Object> recordInspectionAndRemediation(
            String alarmId, String inspectorRole, String findingCode, String actionType, int scrappedUnits
    ) {
        return recordInspectionAndRemediation(alarmId, inspectorRole, findingCode, actionType, scrappedUnits, null);
    }

    public synchronized Map<String, Object> recordInspectionAndRemediation(
            String alarmId, String inspectorRole, String findingCode, String actionType, int scrappedUnits,
            String targetZoneId
    ) {
        Set<String> validRoles = Set.of("QUALITY_ENGINEER", "MAINTENANCE_ENGINEER", "PLANT_OPERATOR", "OT_IT_ADMIN");
        Set<String> validFindings = Set.of(
                "CONFIRMED_EXCURSION", "DOOR_SEAL_FAILURE", "SENSOR_CALIBRATION_DRIFT",
                "SENSOR_COMMS_DROP", "WRONG_ZONE_PLACEMENT", "WITHIN_TOLERANCE"
        );
        Set<String> supportedActions = Set.of(
                "RELOCATE_LOT", "QUARANTINE_AND_SCRAP_PARTIAL", "RELEASE_LOT_AFTER_TEST",
                "RECALIBRATE_SENSOR", "REPAIR_DOOR_CLOSER", "RESTORE_SENSOR_LINK"
        );
        if (!validRoles.contains(inspectorRole)) {
            throw new IllegalArgumentException("Unsupported inspector role: " + inspectorRole);
        }
        if (!validFindings.contains(findingCode)) {
            throw new IllegalArgumentException("Unsupported inspection finding: " + findingCode);
        }
        if (!supportedActions.contains(actionType)) {
            throw new IllegalArgumentException("Unsupported remediation action: " + actionType);
        }
        if (scrappedUnits < 0) {
            throw new IllegalArgumentException("scrappedUnits must not be negative");
        }
        if (!"QUARANTINE_AND_SCRAP_PARTIAL".equals(actionType) && scrappedUnits != 0) {
            throw new IllegalArgumentException("scrappedUnits must be zero for action " + actionType);
        }

        Alarm targetAlarm = alarms.stream().filter(a -> a.alarmId().equals(alarmId)).findFirst()
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Alarm not found: " + alarmId));

        String nowIso = Instant.now().toString();
        String newInsId = String.format("INS-2026-%06d", inspections.size() + 1);
        Inspection newInspection = new Inspection(
                newInsId, alarmId, targetAlarm.zoneId(), inspectorRole,
                nowIso, findingCode, true, "COMPLETED"
        );

        List<AlarmAffectedLot> links = alarmAffectedLots.stream().filter(a -> a.alarmId().equals(alarmId)).toList();
        boolean lotAction = "QUARANTINE_AND_SCRAP_PARTIAL".equals(actionType)
                || "RELEASE_LOT_AFTER_TEST".equals(actionType)
                || "RELOCATE_LOT".equals(actionType);
        if (!"RELOCATE_LOT".equals(actionType) && targetZoneId != null && !targetZoneId.isBlank()) {
            throw new IllegalArgumentException("targetZoneId is only valid for RELOCATE_LOT");
        }
        String targetLotId = lotAction && !links.isEmpty() ? links.get(0).lotId() : "";
        double unitVal = 100.0;
        InventoryLot updatedLot = null;
        ZoneLotAssignment newAssignment = null;
        if (!targetLotId.isBlank()) {
            for (int i = 0; i < inventoryLots.size(); i++) {
                InventoryLot l = inventoryLots.get(i);
                if (l.lotId().equals(targetLotId)) {
                    unitVal = l.unitValueUsd();
                    if (scrappedUnits > l.availableQuantityUnits()) {
                        throw new IllegalArgumentException(
                                "scrappedUnits exceeds available units for lot " + l.lotId()
                        );
                    }
                    int newComp = l.compromisedQuantityUnits() + scrappedUnits;
                    int newAvail = l.initialQuantityUnits() - newComp;
                    if ("RELOCATE_LOT".equals(actionType)) {
                        if (targetZoneId == null || targetZoneId.isBlank()) {
                            throw new IllegalArgumentException("targetZoneId is required to relocate a lot");
                        }
                        Zone destination = zones.stream()
                                .filter(z -> z.zoneId().equals(targetZoneId))
                                .findFirst()
                                .orElseThrow(() -> new IllegalArgumentException("Unknown target zone: " + targetZoneId));
                        StorageRequirement requirement = storageRequirements.stream()
                                .filter(r -> r.requirementId().equals(l.requirementId()))
                                .findFirst()
                                .orElseThrow(() -> new IllegalStateException("Missing storage requirement: " + l.requirementId()));
                        if (!Arrays.asList(requirement.allowedZoneTypes().split(",")).contains(destination.zoneType())) {
                            throw new IllegalArgumentException("Target zone is incompatible with lot " + l.lotId());
                        }
                        newAssignment = new ZoneLotAssignment(
                                String.format("ZLA-2026-%06d", zoneLotAssignments.size() + 1),
                                l.lotId(), destination.zoneId(), nowIso, "", 0.0, true
                        );
                        updatedLot = new InventoryLot(
                                l.lotId(), l.requirementId(), destination.zoneId(), l.productSku(),
                                l.initialQuantityUnits(), l.compromisedQuantityUnits(), l.availableQuantityUnits(),
                                l.unitValueUsd(), l.totalDwellHours(), l.cumulativeExcursionMin(),
                                l.lifecycleState(), l.receivedAt(), l.expirationDate()
                        );
                    } else {
                        String nextState = "QUARANTINE_AND_SCRAP_PARTIAL".equals(actionType)
                                ? "QUARANTINED" : "INSPECTED_RELEASED";
                        updatedLot = new InventoryLot(
                                l.lotId(), l.requirementId(), l.currentZoneId(), l.productSku(),
                                l.initialQuantityUnits(), newComp, newAvail, l.unitValueUsd(),
                                l.totalDwellHours(), l.cumulativeExcursionMin(),
                                nextState,
                                l.receivedAt(), l.expirationDate()
                        );
                    }
                    break;
                }
            }
        }
        if (lotAction && targetLotId.isBlank()) {
            throw new IllegalArgumentException("This remediation requires an alarm linked to an affected lot");
        }

        double laborUsd = 250.0;
        double finImpact = Math.round((scrappedUnits * unitVal + laborUsd) * 100.0) / 100.0;
        String newRemId = String.format("REM-2026-%06d", remediations.size() + 1);
        Remediation newRemediation = new Remediation(
                newRemId, newInsId, alarmId, targetLotId, actionType,
                scrappedUnits, finImpact, laborUsd, nowIso, "VERIFIED_CLOSED"
        );

        WorkflowEvent event = new WorkflowEvent(
                "EVT-" + (auditEventLog.size() + 1),
                nowIso,
                inspectorRole,
                alarmId,
                newInspection,
                newRemediation,
                updatedLot,
                newAssignment
        );
        try {
            appendWorkflowEvent(resolveWorkflowJournalPath(resolveDataDir()), event);
        } catch (IOException e) {
            throw new IllegalStateException("Unable to persist workflow event; no changes were applied", e);
        }
        inspections.add(newInspection);
        remediations.add(newRemediation);
        if (updatedLot != null) {
            replaceLot(updatedLot);
        }
        if (newAssignment != null) {
            zoneLotAssignments.add(newAssignment);
        }
        Map<String, Object> auditEvent = toAuditEvent(event);
        auditEventLog.add(auditEvent);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("status", "RECORDED_APPEND_ONLY");
        result.put("inspection", newInspection);
        result.put("remediation", newRemediation);
        result.put("auditEvent", auditEvent);
        if (newAssignment != null) {
            result.put("assignment", newAssignment);
        }
        return result;
    }

    /**
     * Runs programmatic Step 8 validation checks in Java.
     */
    public List<ValidationCheckResult> runValidationSuite() {
        List<ValidationCheckResult> results = new ArrayList<>();

        // 1. Warehouse capacity == SUM(Zone.capacityPallets)
        int whCapViolations = 0;
        Map<String, Integer> zoneCapByWh = zones.stream()
                .collect(Collectors.groupingBy(Zone::warehouseId, Collectors.summingInt(Zone::capacityPallets)));
        for (Warehouse wh : warehouses) {
            if (wh.totalCapacityPallets() != zoneCapByWh.getOrDefault(wh.warehouseId(), 0)) {
                whCapViolations++;
            }
        }
        results.add(new ValidationCheckResult(
                "Warehouse Capacity Reconciliation", "ARITHMETIC_RECONCILIATION",
                whCapViolations == 0, warehouses.size(), whCapViolations,
                "Warehouse.totalCapacityPallets == SUM(Zone.capacityPallets)"
        ));

        // 2. InventoryLot available == initial - compromised
        int lotViolations = 0;
        for (InventoryLot lot : inventoryLots) {
            if (lot.initialQuantityUnits() - lot.compromisedQuantityUnits() != lot.availableQuantityUnits()) {
                lotViolations++;
            }
        }
        results.add(new ValidationCheckResult(
                "InventoryLot Balance Reconciliation", "ARITHMETIC_RECONCILIATION",
                lotViolations == 0, inventoryLots.size(), lotViolations,
                "availableQuantityUnits == initialQuantityUnits - compromisedQuantityUnits"
        ));

        // 3. Alarm affectedLotCount == COUNT(AlarmAffectedLot)
        Map<String, Long> aalCountByAlarm = alarmAffectedLots.stream()
                .collect(Collectors.groupingBy(AlarmAffectedLot::alarmId, Collectors.counting()));
        int almViolations = 0;
        for (Alarm alm : alarms) {
            if (alm.affectedLotCount() != aalCountByAlarm.getOrDefault(alm.alarmId(), 0L).intValue()) {
                almViolations++;
            }
        }
        results.add(new ValidationCheckResult(
                "Alarm Affected-Lot Bridge Count Reconciliation", "FOREIGN_KEY_AND_BRIDGE",
                almViolations == 0, alarms.size(), almViolations,
                "Alarm.affectedLotCount matches exact count in AlarmAffectedLot bridge table"
        ));

        return results;
    }
}
