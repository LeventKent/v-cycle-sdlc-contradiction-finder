# Firmware Architecture

## Overview

The OpenMower V2 firmware runs on an RP2040 dual-core microcontroller, exposing hardware peripherals as **xbot services**. Each service is an independent module with its own state, communication registers, and lifecycle. The firmware communicates with the ROS layer via UDP (V2) or COBS-encoded serial (V1).

## Dual-Core Design

### Core 0: Application & Communication

- xbot service framework event loop
- Service discovery and registration
- UDP packet handling (V2) or serial COBS framing (V1)
- Sensor polling at defined intervals
- Emergency state machine

### Core 1: Real-Time Motor Control

- PWM generation for ESCs
- Wheel encoder counting (via PIO)
- IMU data acquisition at high frequency
- Time-critical safety interlocks (hardware-level emergency)

## xbot Service Interface Framework

The firmware uses the **xbot service interface** — a lightweight publish/subscribe framework designed for embedded systems. Each service:

1. Has a unique **service ID** (uint16_t)
2. Exposes typed **registers** (read/write properties)
3. Supports **callbacks** when registers are written by the ROS side
4. Participates in **service discovery** via UDP multicast

### Service Lifecycle

```
Service Created → Start() → [Running: handling register reads/writes] → Stop()
                                ↑                                          |
                                └── OnServiceConnected() callback          |
                                     OnServiceDisconnected() callback ←────┘
```

### Service Registration Pattern

On the ROS side, each firmware service has a corresponding `*ServiceInterfaceBase` (auto-generated) and a custom `*ServiceInterface` class:

```cpp
// From mower_comms_v2/src/EmergencyServiceInterface.h
class EmergencyServiceInterface : public EmergencyServiceInterfaceBase {
 public:
  EmergencyServiceInterface(uint16_t service_id, const xbot::serviceif::Context& ctx,
                            const ros::Publisher& publisher)
      : EmergencyServiceInterfaceBase(service_id, ctx), publisher_(publisher) {}

  bool SetHighLevelEmergency(bool new_value);
  void Heartbeat();

 protected:
  void OnEmergencyReasonChanged(const uint16_t& new_value) override;

 private:
  void OnServiceDisconnected(uint16_t service_id) override;
  void PublishEmergencyState();
};
```

## Service Catalog

| Service | ID | Direction | Key Registers |
|---|---|---|---|
| Emergency | 1 | Bidirectional | emergency_reason (R), high_level_emergency (W) |
| DiffDrive | 2 | Bidirectional | target_twist (W), actual_twist (R), wheel_ticks (R), esc_status (R) |
| Mower | 3 | Bidirectional | mow_enabled (W), motor_status (R), temperature (R) |
| IMU | 4 | Read-only | acceleration[3] (R), gyro[3] (R) |
| Power | 5 | Read-only | battery_voltage (R), charge_voltage (R), charge_current (R) |
| BMS | 6 | Read-only | cell_voltages (R), total_voltage (R) |
| GPS | 7 | Bidirectional | gps_data (R), rtcm_data (W), config (W) |
| Input | 8 | Read-only | hall_sensors (R), actions (R) |
| HighLevel | 9 | Bidirectional | high_level_status (W), actions (R) |

## Main Loop Structure

### V2 Firmware (UDP-based)

```
main() {
    hardware_init();           // GPIO, SPI, I2C, UART, ADC
    service_framework_init();  // xbot context, UDP socket
    
    register_services();       // Create all service instances
    
    // Core 1 launched for real-time tasks
    multicore_launch_core1(core1_entry);
    
    // Core 0: service event loop
    while (true) {
        xbot::serviceif::Spin();  // Process incoming UDP packets
        poll_sensors();           // Read IMU, ADC, hall sensors
        update_services();        // Push new values to registers
    }
}
```

### V1 Firmware (Serial-based)

```
main() {
    hardware_init();
    serial_init(115200);
    
    while (true) {
        // Read incoming COBS packets
        if (serial_available()) {
            packet = cobs_decode(serial_read());
            if (crc_valid(packet)) {
                handle_packet(packet);  // Dispatch by packet type ID
            }
        }
        
        // Periodic status transmission
        if (timer_expired(STATUS_INTERVAL)) {
            send_status_packet();   // ll_status struct
            send_imu_packet();      // ll_imu struct
        }
    }
}
```

## Packet Handling Pipeline (V1)

```
Serial RX → COBS Decode → CRC-16 Verify → Type Dispatch → Handler
                                                              ↓
Serial TX ← COBS Encode ← CRC-16 Append ← Response Build ←─┘
```

### V1 Packet Types (from `ll_datatypes.h`)

```cpp
#define PACKET_ID_LL_STATUS 1              // Firmware → ROS: status/sensors
#define PACKET_ID_LL_IMU 2                 // Firmware → ROS: IMU data
#define PACKET_ID_LL_UI_EVENT 3            // Firmware → ROS: button press
#define PACKET_ID_LL_HIGH_LEVEL_CONFIG_REQ 0x11  // Bidirectional config
#define PACKET_ID_LL_HIGH_LEVEL_CONFIG_RSP 0x12  // Config response
#define PACKET_ID_LL_HEARTBEAT 0x42        // ROS → Firmware: heartbeat
#define PACKET_ID_LL_HIGH_LEVEL_STATE 0x43 // ROS → Firmware: state info
```

## Module Integration Pattern

New firmware modules follow this pattern:

### 1. Define the Service Interface (YAML → auto-generated base class)

The xbot framework generates `*ServiceInterfaceBase` classes from service definitions specifying registers, their types, and directions.

### 2. Implement the Custom Service Interface

```cpp
// Example: Adding a WiFi service
class WiFiServiceInterface : public WiFiServiceInterfaceBase {
 public:
  WiFiServiceInterface(uint16_t service_id, const xbot::serviceif::Context& ctx,
                       const ros::Publisher& status_pub)
      : WiFiServiceInterfaceBase(service_id, ctx), status_pub_(status_pub) {}

 protected:
  // Called when firmware reports WiFi status register change
  void OnWiFiStatusChanged(const uint8_t& new_value) override {
    // Publish to ROS topic
  }

  // Called when firmware reports RSSI register change
  void OnRssiChanged(const int8_t& new_value) override {
    // Update ROS message
  }

 private:
  void OnServiceConnected(uint16_t service_id) override { /* init */ }
  void OnServiceDisconnected(uint16_t service_id) override { /* handle timeout */ }
  const ros::Publisher& status_pub_;
};
```

### 3. Register in mower_comms

```cpp
// In mower_comms.cpp main():
auto wifi_service = std::make_unique<WiFiServiceInterface>(
    SERVICE_ID_WIFI, ctx, wifi_status_pub);
wifi_service->Start();
```

### 4. Add Service ID

```cpp
// In service_ids.h or equivalent:
namespace xbot::service_ids {
  constexpr uint16_t WIFI = 10;  // Next available ID
}
```

## Configuration Flow

```
YAML params → ROS param server → mower_comms_v2 reads at startup
                                        ↓
              Firmware service ← OnConfigurationRequested() callback
```

Example from DiffDrive:
```cpp
bool DiffDriveServiceInterface::OnConfigurationRequested(uint16_t service_id) {
  // Send ticks_per_m and wheel_distance_m to firmware
  SetWheelTicksPerMeter(ticks_per_meter_);
  SetWheelDistance(wheel_distance_);
  return true;
}
```

## Cross-References

- Hardware interfaces: [03-Hardware-Architecture.md](03-Hardware-Architecture.md)
- Communication protocol details: [06-Communication-Protocols.md](06-Communication-Protocols.md)
- ROS-side integration: [07-Software-Architecture.md](07-Software-Architecture.md)
- Emergency handling: [09-Safety-Systems.md](09-Safety-Systems.md)
