# Communication Protocols

## Overview

OpenMower uses a layered communication architecture: firmware-to-ROS communication (low-level) and ROS inter-node communication (high-level). Two firmware protocol versions exist — V1 (serial) and V2 (UDP) — selected at runtime via the `HARDWARE_PLATFORM` environment variable.

## Firmware ↔ ROS Communication

### V2 Protocol: xbot Service Interface over UDP

The modern protocol uses UDP multicast on a dedicated subnet between the RP2040 mainboard and the Raspberry Pi.

**Network Configuration:**
- Subnet: `172.16.78.0/24`
- Mainboard IP: `172.16.78.1`
- Bind address (ROS side): configurable via `ll/bind_ip` param (default `0.0.0.0`)
- Transport: UDP with service discovery via multicast

**Service Discovery Flow:**
1. Firmware broadcasts service advertisements (service ID, version, capabilities)
2. ROS `mower_comms_v2` listens for advertisements and creates service interface instances
3. Once connected, register reads/writes flow as individual UDP packets
4. Heartbeat mechanism detects disconnection (triggers `TIMEOUT_HIGH_LEVEL`)

**Register-Based Communication:**
Each service exposes typed registers. Changes are pushed automatically:
```
Firmware writes register → UDP packet → ROS callback (On*Changed)
ROS writes register → UDP packet → Firmware applies value
```

**Startup sequence from `mower_comms.cpp`:**
```cpp
// Initialize xbot service interface framework
xbot::serviceif::SetShutdownCallback([] { ros::requestShutdown(); });
ctx = xbot::serviceif::Start(true, bind_ip);

// Create and start each service
emergency_service = std::make_unique<EmergencyServiceInterface>(
    xbot::service_ids::EMERGENCY, ctx, emergency_pub);
emergency_service->Start();
// ... repeat for each service
```

### V1 Protocol: COBS over Serial UART

The legacy protocol uses a serial UART connection with COBS (Consistent Overhead Byte Stuffing) framing.

**Connection:**
- Interface: `/dev/ttyAMA0` or similar (Raspberry Pi UART)
- Baud rate: 115200
- Framing: COBS encoding (0x00 as frame delimiter)
- Integrity: CRC-16 CCITT appended to each packet

**Packet Structure:**
```
[COBS-encoded payload][0x00 delimiter]

Decoded payload:
[type: uint8_t][data: variable][crc: uint16_t]
```

**Key Data Structures (from `ll_datatypes.h`):**

```cpp
// Firmware → ROS: Full status (PACKET_ID_LL_STATUS = 1)
struct ll_status {
  uint8_t type;              // = 1
  uint8_t status_bitmask;   // Bit 0: Initialized, 1: RasPi power, 2: Charging,
                             // 3: ESC power, 4: Rain, 5: Sound avail, 6: Sound busy, 7: UI board
  float uss_ranges_m[5];    // Ultrasonic sensor ranges
  uint8_t emergency_bitmask;// Bit 0: Latch, 1: Stop, 2: Lift
  float v_charge;           // Charge voltage
  float v_system;           // System voltage
  float charging_current;   // Charge current
  uint8_t batt_percentage;  // Battery level
  uint16_t crc;
} __attribute__((packed));

// Firmware → ROS: IMU data (PACKET_ID_LL_IMU = 2)
struct ll_imu {
  uint8_t type;              // = 2
  uint16_t dt_millis;        // Time since last message
  float acceleration_mss[3]; // m/s²
  float gyro_rads[3];        // rad/s
  float mag_uT[3];           // µT (magnetometer)
  uint16_t crc;
} __attribute__((packed));

// ROS → Firmware: Heartbeat (PACKET_ID_LL_HEARTBEAT = 0x42)
struct ll_heartbeat {
  uint8_t type;                      // = 0x42
  uint8_t emergency_requested;       // Set to latch emergency
  uint8_t emergency_release_requested; // Set to clear emergency
  uint16_t crc;
} __attribute__((packed));
```

## ROS Inter-Node Communication

### Key Topics

| Topic | Type | Publisher | Subscribers | Rate |
|---|---|---|---|---|
| `/ll/emergency` | `mower_msgs/Emergency` | mower_comms | mower_logic | Event-driven |
| `/ll/mower_status` | `mower_msgs/Status` | mower_comms | mower_logic | ~10 Hz |
| `/ll/power` | `mower_msgs/Power` | mower_comms | mower_logic | ~5 Hz |
| `/ll/bms` | `mower_msgs/Bms` | mower_comms | mower_logic | ~1 Hz |
| `/ll/diff_drive/measured_twist` | `TwistStamped` | mower_comms | xbot_positioning | ~50 Hz |
| `/ll/diff_drive/left_esc_status` | `mower_msgs/ESCStatus` | mower_comms | mower_logic | ~10 Hz |
| `/ll/diff_drive/right_esc_status` | `mower_msgs/ESCStatus` | mower_comms | mower_logic | ~10 Hz |
| `/ll/imu/data_raw` | `sensor_msgs/Imu` | mower_comms | xbot_positioning | ~100 Hz |
| `/ll/position/gps` | `xbot_msgs/AbsolutePose` | mower_comms | xbot_positioning | ~10 Hz |
| `/ll/cmd_vel` | `geometry_msgs/Twist` | twist_mux | mower_comms | ~50 Hz |
| `/xbot_positioning/xb_pose` | `xbot_msgs/AbsolutePose` | xbot_positioning | mower_logic | ~50 Hz |
| `/mower_logic/current_state` | `HighLevelStatus` | mower_logic | xbot_monitoring, app | 1 Hz |
| `/xbot/action` | `std_msgs/String` | mower_comms, monitoring | mower_logic | Event-driven |

### Key Services

| Service | Type | Server | Purpose |
|---|---|---|---|
| `mower_service/high_level_control` | `HighLevelControlSrv` | mower_logic | START/HOME/S1/S2/RESET |
| `ll/_service/mow_enabled` | `MowerControlSrv` | mower_comms | Enable/disable blade |
| `ll/_service/emergency` | `EmergencyStopSrv` | mower_comms | Set/clear high-level emergency |
| `mower_map_service/get_mowing_area` | `GetMowingAreaSrv` | mower_map | Retrieve area boundaries |
| `mower_map_service/get_docking_point` | `GetDockingPointSrv` | mower_map | Retrieve dock pose |
| `xbot_positioning/set_gps_state` | `GPSControlSrv` | xbot_positioning | Enable/disable GPS fusion |
| `xbot_positioning/set_robot_pose` | `SetPoseSrv` | xbot_positioning | Override EKF pose |

### Message Definitions

```
# mower_msgs/Emergency.msg
time stamp
bool active_emergency
bool latched_emergency
string reason

# mower_msgs/HighLevelStatus.msg
uint8 state               # IDLE=1, AUTONOMOUS=2, RECORDING=3
string state_name
string sub_state_name
string job_id
string session_id
int16 current_area
float32 gps_quality_percent
float32 battery_percent
bool is_charging
bool emergency

# mower_msgs/HighLevelControlSrv.srv
uint8 COMMAND_START=1
uint8 COMMAND_HOME=2
uint8 COMMAND_S1=3
uint8 COMMAND_S2=4
uint8 COMMAND_RESET_EMERGENCY=254
uint8 COMMAND_DELETE_MAPS=255
uint8 command
---
```

## Velocity Command Arbitration

```
/logic_vel (mower_logic/move_base) ─┐
/joy_vel (gamepad/remote) ──────────┼─→ twist_mux → /ll/cmd_vel → firmware
/xbot_remote/cmd_vel (remote) ──────┘

Priority (from twist_mux_topics.yaml):
  1. Emergency stop (all zero)
  2. Joystick (manual override)
  3. Navigation (autonomous)
```

## Pattern for Adding New Communication Channels

### Adding a new firmware service (V2):

1. **Define service registers** in xbot service YAML definition
2. **Implement firmware-side service** handling register reads/writes
3. **Create `*ServiceInterface` class** in `mower_comms_v2/src/` inheriting generated base
4. **Instantiate and start** in `mower_comms.cpp` main()
5. **Add ROS publishers/subscribers** for the new data channels
6. **Register service ID** in the shared service_ids header

### Adding a new ROS topic/service:

1. **Define message/service** in `mower_msgs/msg/` or `mower_msgs/srv/`
2. **Update CMakeLists.txt** to include new message in generation
3. **Create publisher/subscriber** in relevant node
4. **Update launch files** if new nodes or remappings needed

## RTCM Correction Data Flow

```
NTRIP Server → ros_ntrip_client → /ll/position/gps/rtcm → mower_comms_v2
                                                                ↓
                                              GPS service → UART → u-blox module
```

Buffering: RTCM data is accumulated and sent at max 5 Hz with max 1000-byte packets to avoid spamming the GPS module.

## Cross-References

- Firmware service framework: [05-Firmware-Architecture.md](05-Firmware-Architecture.md)
- ROS software architecture: [07-Software-Architecture.md](07-Software-Architecture.md)
- Safety-related communication: [09-Safety-Systems.md](09-Safety-Systems.md)
