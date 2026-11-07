package ai.yottaflex.telemetry.controller;

import ai.yottaflex.telemetry.model.DomainModels.*;
import ai.yottaflex.telemetry.service.TelemetryDataService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.*;

@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "*", allowedHeaders = "*")
public class TelemetryController {

    private final TelemetryDataService dataService;

    public TelemetryController(TelemetryDataService dataService) {
        this.dataService = dataService;
    }

    @GetMapping("/overview")
    public Map<String, Object> getOverview() {
        Map<String, Object> eval = dataService.evaluateEdgeCasesAndGroundTruth();
        double totalFinancialImpact = dataService.getRemediations().stream()
                .mapToDouble(Remediation::financialImpactUsd).sum();
        long excursionReadings = dataService.getSensorReadings().stream()
                .filter(SensorReading::isExcursion).count();
        long gapReadings = dataService.getSensorReadings().stream()
                .filter(SensorReading::isGapAfterPrev).count();

        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("fixedSeed", 20261022);
        summary.put("warehousesCount", dataService.getWarehouses().size());
        summary.put("zonesCount", dataService.getZones().size());
        summary.put("sensorsCount", dataService.getSensors().size());
        summary.put("sensorReadingsLoaded", dataService.getSensorReadings().size());
        summary.put("doorEventsCount", dataService.getDoorEvents().size());
        summary.put("inventoryLotsCount", dataService.getInventoryLots().size());
        summary.put("alarmsCount", dataService.getAlarms().size());
        summary.put("inspectionsCount", dataService.getInspections().size());
        summary.put("remediationsCount", dataService.getRemediations().size());
        summary.put("excursionReadingsCount", excursionReadings);
        summary.put("explicitGapReadingsCount", gapReadings);
        summary.put("totalFinancialImpactUsd", Math.round(totalFinancialImpact * 100.0) / 100.0);
        summary.put("groundTruthEvaluation", Map.of(
                "totalDetectedExceptions", eval.get("totalDetectedExceptions"),
                "totalGroundTruthLabels", eval.get("totalGroundTruthLabels"),
                "precisionPct", eval.get("precisionPct"),
                "recallPct", eval.get("recallPct"),
                "f1ScorePct", eval.get("f1ScorePct")
        ));
        return summary;
    }

    @GetMapping("/warehouses")
    public List<Warehouse> getWarehouses() {
        return dataService.getWarehouses();
    }

    @GetMapping("/sensors")
    public List<Sensor> getSensors() {
        return dataService.getSensors();
    }

    @GetMapping("/sensor-zone-mappings")
    public List<SensorZoneMapping> getSensorZoneMappings() {
        return dataService.getSensorMappings();
    }

    @GetMapping("/readings")
    public List<SensorReading> getReadings(
            @RequestParam(required = false) String zoneId,
            @RequestParam(defaultValue = "15000") int limit
    ) {
        validateLimit(limit, 100000);
        return dataService.getSensorReadings().stream()
                .filter(r -> zoneId == null || zoneId.isBlank() || r.zoneId().equalsIgnoreCase(zoneId))
                .limit(limit)
                .toList();
    }

    @GetMapping("/door-events")
    public List<DoorEvent> getDoorEvents(@RequestParam(required = false) String zoneId) {
        return dataService.getDoorEvents().stream()
                .filter(d -> zoneId == null || zoneId.isBlank() || d.zoneId().equalsIgnoreCase(zoneId))
                .toList();
    }

    @GetMapping("/storage-requirements")
    public List<StorageRequirement> getStorageRequirements() {
        return dataService.getStorageRequirements();
    }

    @GetMapping("/zone-lot-assignments")
    public List<ZoneLotAssignment> getZoneLotAssignments() {
        return dataService.getZoneLotAssignments();
    }

    @GetMapping("/alarm-affected-lots")
    public List<AlarmAffectedLot> getAlarmAffectedLots() {
        return dataService.getAlarmAffectedLots();
    }

    @GetMapping("/ground-truth")
    public List<GroundTruthItem> getGroundTruth() {
        return dataService.getGroundTruthItems();
    }

    @GetMapping("/zones")
    public List<Zone> getZones(@RequestParam(required = false) String warehouseId) {
        if (warehouseId == null || warehouseId.isBlank()) {
            return dataService.getZones();
        }
        return dataService.getZones().stream()
                .filter(z -> z.warehouseId().equalsIgnoreCase(warehouseId))
                .toList();
    }

    @GetMapping("/zones/{zoneId}/telemetry")
    public ResponseEntity<Map<String, Object>> getZoneTelemetry(@PathVariable String zoneId) {
        Optional<Zone> zoneOpt = dataService.getZones().stream()
                .filter(z -> z.zoneId().equalsIgnoreCase(zoneId)).findFirst();
        if (zoneOpt.isEmpty()) {
            return ResponseEntity.notFound().build();
        }
        List<Sensor> zoneSensors = dataService.getSensors().stream()
                .filter(s -> s.primaryZoneId().equalsIgnoreCase(zoneId)).toList();
        List<SensorReading> readings = dataService.getSensorReadings().stream()
                .filter(r -> r.zoneId().equalsIgnoreCase(zoneId)).limit(200).toList();
        List<DoorEvent> doors = dataService.getDoorEvents().stream()
                .filter(d -> d.zoneId().equalsIgnoreCase(zoneId)).toList();
        List<InventoryLot> lots = dataService.getInventoryLots().stream()
                .filter(l -> l.currentZoneId().equalsIgnoreCase(zoneId)).toList();
        List<Alarm> alarms = dataService.getAlarms().stream()
                .filter(a -> a.zoneId().equalsIgnoreCase(zoneId)).toList();

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("zone", zoneOpt.get());
        payload.put("sensors", zoneSensors);
        payload.put("readings", readings);
        payload.put("doorEvents", doors);
        payload.put("storedLots", lots);
        payload.put("alarms", alarms);
        return ResponseEntity.ok(payload);
    }

    @GetMapping("/lots")
    public List<InventoryLot> getLots(
            @RequestParam(required = false) String zoneId,
            @RequestParam(required = false) String state,
            @RequestParam(defaultValue = "100") int limit
    ) {
        validateLimit(limit, 10000);
        return dataService.getInventoryLots().stream()
                .filter(l -> zoneId == null || zoneId.isBlank() || l.currentZoneId().equalsIgnoreCase(zoneId))
                .filter(l -> state == null || state.isBlank() || l.lifecycleState().equalsIgnoreCase(state))
                .limit(limit)
                .toList();
    }

    @GetMapping("/lots/{lotId}/traceability")
    public ResponseEntity<LotTraceabilityView> getLotTraceability(@PathVariable String lotId) {
        return dataService.getLotTraceability(lotId)
                .map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.notFound().build());
    }

    @GetMapping("/alarms")
    public List<Alarm> getAlarms(@RequestParam(required = false) String severity) {
        if (severity == null || severity.isBlank()) {
            return dataService.getAlarms();
        }
        return dataService.getAlarms().stream()
                .filter(a -> a.severity().equalsIgnoreCase(severity))
                .toList();
    }

    @GetMapping("/inspections")
    public List<Inspection> getInspections() {
        return dataService.getInspections();
    }

    @GetMapping("/remediations")
    public List<Remediation> getRemediations() {
        return dataService.getRemediations();
    }

    @GetMapping("/audit-events")
    public List<Map<String, Object>> getAuditEvents() {
        return dataService.getAuditEventLog();
    }

    @PostMapping("/alarms/{alarmId}/remediate")
    public ResponseEntity<Map<String, Object>> remediateAlarm(
            @PathVariable String alarmId,
            @RequestParam(defaultValue = "QUALITY_ENGINEER") String inspectorRole,
            @RequestParam(defaultValue = "CONFIRMED_EXCURSION") String findingCode,
            @RequestParam(defaultValue = "QUARANTINE_AND_SCRAP_PARTIAL") String actionType,
            @RequestParam(defaultValue = "10") int scrappedUnits,
            @RequestParam(required = false) String targetZoneId
    ) {
        Map<String, Object> out = dataService.recordInspectionAndRemediation(
                alarmId, inspectorRole, findingCode, actionType, scrappedUnits, targetZoneId
        );
        return ResponseEntity.ok(out);
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, String>> handleInvalidRequest(IllegalArgumentException exception) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(Map.of("error", exception.getMessage()));
    }

    @GetMapping("/exceptions/evaluate")
    public Map<String, Object> evaluateExceptions() {
        return dataService.evaluateEdgeCasesAndGroundTruth();
    }

    @GetMapping("/validation/report")
    public List<ValidationCheckResult> getValidationReport() {
        return dataService.runValidationSuite();
    }

    private void validateLimit(int limit, int maximum) {
        if (limit < 1 || limit > maximum) {
            throw new IllegalArgumentException("limit must be between 1 and " + maximum);
        }
    }
}
