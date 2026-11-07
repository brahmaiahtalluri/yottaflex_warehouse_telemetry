import warehousesUrl from '../../data/seed/json/warehouses.json?url';
import zonesUrl from '../../data/seed/json/zones.json?url';
import sensorsUrl from '../../data/seed/json/sensors.json?url';
import sensorMappingsUrl from '../../data/seed/json/sensor_zone_mapping_history.json?url';
import readingsUrl from '../../data/seed/json/sensor_readings.json?url';
import doorEventsUrl from '../../data/seed/json/door_events.json?url';
import storageRequirementsUrl from '../../data/seed/json/storage_requirements.json?url';
import inventoryLotsUrl from '../../data/seed/json/inventory_lots.json?url';
import zoneLotAssignmentsUrl from '../../data/seed/json/zone_lot_assignments.json?url';
import alarmsUrl from '../../data/seed/json/alarms.json?url';
import alarmAffectedLotsUrl from '../../data/seed/json/alarm_affected_lots.json?url';
import inspectionsUrl from '../../data/seed/json/inspections.json?url';
import remediationsUrl from '../../data/seed/json/remediations.json?url';
import groundTruthUrl from '../../data/seed/ground_truth.json?url';

async function loadJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Could not load generated seed data (${response.status}): ${url}`);
  }
  return response.json();
}

export async function loadSeedData() {
  const [
    warehouses,
    zones,
    sensors,
    sensorMappings,
    readings,
    doorEvents,
    storageRequirements,
    inventoryLots,
    zoneLotAssignments,
    alarms,
    alarmAffectedLots,
    inspections,
    remediations,
    groundTruth,
  ] = await Promise.all([
    loadJson(warehousesUrl),
    loadJson(zonesUrl),
    loadJson(sensorsUrl),
    loadJson(sensorMappingsUrl),
    loadJson(readingsUrl),
    loadJson(doorEventsUrl),
    loadJson(storageRequirementsUrl),
    loadJson(inventoryLotsUrl),
    loadJson(zoneLotAssignmentsUrl),
    loadJson(alarmsUrl),
    loadJson(alarmAffectedLotsUrl),
    loadJson(inspectionsUrl),
    loadJson(remediationsUrl),
    loadJson(groundTruthUrl),
  ]);
  return {
    warehouses,
    zones,
    sensors,
    sensorMappings,
    readings,
    doorEvents,
    storageRequirements,
    inventoryLots,
    zoneLotAssignments,
    alarms,
    alarmAffectedLots,
    inspections,
    remediations,
    groundTruth,
  };
}
