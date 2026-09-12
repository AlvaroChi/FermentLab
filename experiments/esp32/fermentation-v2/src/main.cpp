#include <Arduino.h>

#include "JsonlEmitter.h"
#include "SimulatorSensorHub.h"

namespace {

constexpr char DEVICE_ID[] = "esp32s3-v2-sim-01";
constexpr char SESSION_ID[] = "v2-sim-session-001";
constexpr char* VESSEL_IDS[] = {"vessel-1", "vessel-2", "vessel-3"};
constexpr uint64_t SAMPLE_INTERVAL_MS = 60000;
constexpr uint32_t SIMULATOR_CYCLE_DELAY_MS = 2000;

SimulatorSensorHub simulator;
SensorHub& sensorHub = simulator;
JsonlEmitter emitter(DEVICE_ID, SESSION_ID);
uint64_t sequence = 0;

}  // namespace

void setup() {
  Serial.begin(115200);
  sensorHub.begin();
}

void loop() {
  const uint64_t elapsedMs = sequence * SAMPLE_INTERVAL_MS;
  for (const char* vesselId : VESSEL_IDS) {
    const VesselSample sample =
        sensorHub.readVessel(vesselId, sequence, elapsedMs);
    emitter.emitSample(sample, Serial);
  }
  ++sequence;
  delay(SIMULATOR_CYCLE_DELAY_MS);
}
