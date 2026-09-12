#include <Arduino.h>

#ifdef FERMENTLAB_TEST_I2C_SCAN

#include <Wire.h>

namespace {
constexpr int I2C_SDA_PIN = 8;
constexpr int I2C_SCL_PIN = 9;
constexpr uint32_t I2C_FREQUENCY_HZ = 100000;
constexpr uint32_t SCAN_INTERVAL_MS = 3000;

const char* knownDevice(uint8_t address) {
  switch (address) {
    case 0x29: return "VL53L4CD ToF";
    case 0x44: return "SHT31 (ADDR low)";
    case 0x45: return "SHT31 (ADDR high)";
    case 0x68: return "DS3231 RTC";
    case 0x70: return "TCA9548A (A0-A2 low)";
    default:
      if (address >= 0x50 && address <= 0x57) {
        return "AT24C32 EEPROM";
      }
      return "unknown";
  }
}

void scanI2c() {
  uint8_t count = 0;
  Serial.println("\nI2C scan");
  for (uint8_t address = 1; address < 127; ++address) {
    Wire.beginTransmission(address);
    const uint8_t error = Wire.endTransmission();
    if (error == 0) {
      Serial.printf("  0x%02X  %s\n", address, knownDevice(address));
      ++count;
    } else if (error == 4) {
      Serial.printf("  0x%02X  bus error\n", address);
    }
  }
  Serial.printf("Found: %u device(s)\n", count);
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("FermentLab V2 hardware test: I2C scanner");
  Serial.printf("SDA=GPIO%d SCL=GPIO%d frequency=%lu Hz\n",
                I2C_SDA_PIN, I2C_SCL_PIN,
                static_cast<unsigned long>(I2C_FREQUENCY_HZ));
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN, I2C_FREQUENCY_HZ);
}

void loop() {
  scanI2c();
  delay(SCAN_INTERVAL_MS);
}

#else

#include "JsonlEmitter.h"
#include "SimulatorSensorHub.h"

namespace {

constexpr char DEVICE_ID[] = "esp32s3-v2-sim-01";
constexpr char SESSION_ID[] = "v2-sim-session-001";
constexpr const char* VESSEL_IDS[] = {"vessel-1", "vessel-2", "vessel-3"};
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

#endif
