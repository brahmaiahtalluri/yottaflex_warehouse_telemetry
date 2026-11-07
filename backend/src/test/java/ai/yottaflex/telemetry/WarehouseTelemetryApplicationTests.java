package ai.yottaflex.telemetry;

import ai.yottaflex.telemetry.model.DomainModels.*;
import ai.yottaflex.telemetry.service.TelemetryDataService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.util.ReflectionTestUtils;

import java.nio.file.Paths;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
class WarehouseTelemetryApplicationTests {

    private static final String WORKFLOW_JOURNAL = Paths.get(
            System.getProperty("java.io.tmpdir"),
            "warehouse-telemetry-tests-" + UUID.randomUUID(),
            "workflow-events.jsonl"
    ).toString();

    @DynamicPropertySource
    static void workflowJournalLocation(DynamicPropertyRegistry registry) {
        registry.add("telemetry.workflow-journal", () -> WORKFLOW_JOURNAL);
    }

    @Autowired
    private TelemetryDataService dataService;

    @Test
    void contextLoadsAndMasterDataConformsToBaseline() {
        assertEquals(10, dataService.getWarehouses().size(), "Should load 10 warehouses");
        assertEquals(100, dataService.getZones().size(), "Should load 100 zones");
        assertEquals(500, dataService.getSensors().size(), "Should load 500 sensors");
        assertTrue(dataService.getSensorReadings().size() >= 15000, "Should load baseline sensor readings");
        assertTrue(dataService.getInventoryLots().size() >= 500, "Should load inventory lots");
    }

    @Test
    void detectsAllFourRequiredEdgeCasesWith100PercentF1Score() {
        Map<String, Object> eval = dataService.evaluateEdgeCasesAndGroundTruth();
        assertEquals(100.0, (Double) eval.get("precisionPct"), "Precision against ground_truth should be 100%");
        assertEquals(100.0, (Double) eval.get("recallPct"), "Recall against ground_truth should be 100%");
        assertEquals(100.0, (Double) eval.get("f1ScorePct"), "F1 score against ground_truth should be 100%");
    }

    @Test
    void validatesArithmeticReconciliationAndReferentialIntegrity() {
        List<ValidationCheckResult> results = dataService.runValidationSuite();
        assertFalse(results.isEmpty());
        for (ValidationCheckResult check : results) {
            assertTrue(check.passed(), "Validation check failed: " + check.checkName());
            assertEquals(0, check.violationsFound(), "Expected 0 violations for " + check.checkName());
        }
    }

    @Test
    void preservesTraceabilityAndAppendsRemediationWithoutOverwritingHistory() {
        Optional<LotTraceabilityView> traceOpt = dataService.getLotTraceability("LOT-2026-000015");
        assertTrue(traceOpt.isPresent(), "LOT-2026-000015 should exist");
        assertFalse(traceOpt.get().zoneCompatible(), "LOT-2026-000015 is an incompatible-zone edge case");

        int initialInspections = dataService.getInspections().size();
        int initialRemediations = dataService.getRemediations().size();
        String firstAlarmId = dataService.getAlarms().get(0).alarmId();

        dataService.recordInspectionAndRemediation(
                firstAlarmId, "QUALITY_ENGINEER", "CONFIRMED_EXCURSION", "QUARANTINE_AND_SCRAP_PARTIAL", 5
        );

        assertEquals(initialInspections + 1, dataService.getInspections().size(), "Should append new inspection record");
        assertEquals(initialRemediations + 1, dataService.getRemediations().size(), "Should append new remediation record");
    }

    @Test
    void workflowEventsAreDurableAndInvalidRemediationsAreRejected(@TempDir Path tempDir) {
        String journal = tempDir.resolve("workflow-events.jsonl").toString();
        TelemetryDataService firstRun = newService(journal);
        String alarmId = firstRun.getAlarms().get(0).alarmId();
        int initialInspections = firstRun.getInspections().size();
        int initialRemediations = firstRun.getRemediations().size();

        assertThrows(IllegalArgumentException.class, () -> firstRun.recordInspectionAndRemediation(
                alarmId, "QUALITY_ENGINEER", "CONFIRMED_EXCURSION", "RESTORE_SENSOR_LINK", -1
        ));
        assertEquals(initialInspections, firstRun.getInspections().size());

        firstRun.recordInspectionAndRemediation(
                alarmId, "OT_IT_ADMIN", "SENSOR_COMMS_DROP", "RESTORE_SENSOR_LINK", 0
        );
        assertEquals(initialInspections + 1, firstRun.getInspections().size());
        assertEquals(initialRemediations + 1, firstRun.getRemediations().size());

        TelemetryDataService restartedService = newService(journal);

        assertEquals(initialInspections + 1, restartedService.getInspections().size());
        assertEquals(initialRemediations + 1, restartedService.getRemediations().size());
        assertEquals(1, restartedService.getAuditEventLog().size());
        assertTrue(Path.of(journal).toFile().isFile());
    }

    @Test
    void relocationRequiresAndPersistsACompatibleDestination(@TempDir Path tempDir) {
        String journal = tempDir.resolve("relocation-events.jsonl").toString();
        TelemetryDataService firstRun = newService(journal);
        AlarmAffectedLot affectedLot = firstRun.getAlarmAffectedLots().get(0);
        Alarm alarm = firstRun.getAlarms().stream()
                .filter(row -> row.alarmId().equals(affectedLot.alarmId()))
                .findFirst().orElseThrow();
        InventoryLot lot = firstRun.getInventoryLots().stream()
                .filter(row -> row.lotId().equals(affectedLot.lotId()))
                .findFirst().orElseThrow();
        StorageRequirement requirement = firstRun.getStorageRequirements().stream()
                .filter(row -> row.requirementId().equals(lot.requirementId()))
                .findFirst().orElseThrow();
        String destinationZoneId = firstRun.getZones().stream()
                .filter(zone -> !zone.zoneId().equals(lot.currentZoneId()))
                .filter(zone -> List.of(requirement.allowedZoneTypes().split(",")).contains(zone.zoneType()))
                .map(Zone::zoneId)
                .findFirst().orElseThrow();

        Map<String, Object> result = firstRun.recordInspectionAndRemediation(
                alarm.alarmId(), "QUALITY_ENGINEER", "CONFIRMED_EXCURSION",
                "RELOCATE_LOT", 0, destinationZoneId
        );
        assertNotNull(result.get("assignment"));
        assertEquals(destinationZoneId, firstRun.getLotTraceability(lot.lotId()).orElseThrow().lot().currentZoneId());

        TelemetryDataService restartedService = newService(journal);
        assertEquals(destinationZoneId,
                restartedService.getLotTraceability(lot.lotId()).orElseThrow().lot().currentZoneId());
        assertTrue(restartedService.getZoneLotAssignments().stream()
                .anyMatch(assignment -> assignment.exitedAt().isBlank()
                        && assignment.zoneId().equals(destinationZoneId)
                        && assignment.lotId().equals(lot.lotId())));
    }

    private TelemetryDataService newService(String journal) {
        TelemetryDataService service = new TelemetryDataService(new ObjectMapper());
        ReflectionTestUtils.setField(service, "configuredDataDir", "../data/seed");
        ReflectionTestUtils.setField(service, "configuredWorkflowJournalPath", journal);
        service.init();
        return service;
    }
}
