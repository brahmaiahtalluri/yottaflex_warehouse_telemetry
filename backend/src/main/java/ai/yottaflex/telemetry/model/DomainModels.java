package ai.yottaflex.telemetry.model;

import java.util.List;
// import java.util.Map;

/**
 * Domain Records for all 10 Core Entities, 3 Bridge Tables, and Evaluation DTOs.
 */
public class DomainModels {

    public record Warehouse(
            String warehouseId,
            String warehouseName,
            String region,
            String facilityType,
            int totalCapacityPallets,
            int activeZoneCount,
            String lifecycleState,
            String effectiveFrom,
            String effectiveTo
    ) {}

    public record Zone(
            String zoneId,
            String warehouseId,
            String zoneName,
            String zoneType,
            double tempMinC,
            double tempMaxC,
            double humidityMinPct,
            double humidityMaxPct,
            int maxOccupancyPersons,
            int capacityPallets,
            String lifecycleState,
            String effectiveFrom
    ) {}

    public record Sensor(
            String sensorId,
            String primaryZoneId,
            String sensorType,
            String unit,
            int samplingIntervalSec,
            double driftRatePerDay,
            String calibrationDueDate,
            String lifecycleState,
            String installedAt
    ) {}

    public record SensorZoneMapping(
            String mappingId,
            String sensorId,
            String zoneId,
            String mappingRationale,
            String effectiveFrom,
            String effectiveTo
    ) {}

    public record SensorReading(
            String readingId,
            String sensorId,
            String zoneId,
            String recordedAt,
            double value,
            String unit,
            int deltaPrevSec,
            boolean isExcursion,
            boolean isGapAfterPrev,
            String qualityStatus
    ) {}

    public record DoorEvent(
            String doorEventId,
            String zoneId,
            String sensorId,
            String openedAt,
            String closedAt,
            int openDurationSec,
            String triggerActor,
            boolean causedExcursion
    ) {}

    public record StorageRequirement(
            String requirementId,
            String productCategory,
            double reqTempMinC,
            double reqTempMaxC,
            double reqHumidityMinPct,
            double reqHumidityMaxPct,
            int maxExcursionMinutes,
            String allowedZoneTypes
    ) {}

    public record InventoryLot(
            String lotId,
            String requirementId,
            String currentZoneId,
            String productSku,
            int initialQuantityUnits,
            int compromisedQuantityUnits,
            int availableQuantityUnits,
            double unitValueUsd,
            double totalDwellHours,
            int cumulativeExcursionMin,
            String lifecycleState,
            String receivedAt,
            String expirationDate
    ) {}

    public record ZoneLotAssignment(
            String assignmentId,
            String lotId,
            String zoneId,
            String enteredAt,
            String exitedAt,
            double dwellHours,
            boolean isZoneCompatible
    ) {}

    public record Alarm(
            String alarmId,
            String zoneId,
            String triggerSensorId,
            String alarmType,
            String severity,
            String triggeredAt,
            String resolvedAt,
            int durationMinutes,
            double peakValue,
            double thresholdLimit,
            int affectedLotCount,
            String lifecycleState
    ) {}

    public record AlarmAffectedLot(
            String alarmLotId,
            String alarmId,
            String lotId,
            int overlapMinutes,
            double riskScore
    ) {}

    public record Inspection(
            String inspectionId,
            String alarmId,
            String zoneId,
            String inspectorRole,
            String inspectedAt,
            String findingCode,
            boolean requiresRemediation,
            String lifecycleState
    ) {}

    public record Remediation(
            String remediationId,
            String inspectionId,
            String alarmId,
            String affectedLotId,
            String actionType,
            int scrappedUnits,
            double financialImpactUsd,
            double laborCostUsd,
            String completedAt,
            String lifecycleState
    ) {}

    public record WorkflowEvent(
            String eventId,
            String timestamp,
            String actorRole,
            String alarmId,
            Inspection inspection,
            Remediation remediation,
            InventoryLot updatedLot,
            ZoneLotAssignment newAssignment
    ) {}

    public record GroundTruthItem(
            String groundTruthId,
            String issueType,
            String entityType,
            String entityId,
            String zoneId,
            String relatedEntityId,
            String expectedDecision,
            String severity,
            String detectedAt,
            String description
    ) {}

    public record DetectedException(
            String issueType,
            String entityType,
            String entityId,
            String zoneId,
            String relatedEntityId,
            String recommendedDecision,
            String severity,
            String rationale,
            boolean matchesGroundTruth
    ) {}

    public record LotTraceabilityView(
            InventoryLot lot,
            StorageRequirement requirement,
            Zone currentZone,
            List<ZoneLotAssignment> assignments,
            List<Alarm> overlappingAlarms,
            List<AlarmAffectedLot> alarmLinks,
            List<Inspection> inspections,
            List<Remediation> remediations,
            boolean zoneCompatible,
            double totalFinancialRiskUsd
    ) {}

    public record ValidationCheckResult(
            String checkName,
            String category,
            boolean passed,
            int recordsEvaluated,
            int violationsFound,
            String details
    ) {}
}
