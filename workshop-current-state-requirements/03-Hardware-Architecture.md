# Hardware Architecture

## Overview

The OpenMower mainboard is a custom PCB built around the RP2040 microcontroller. It provides interfaces for motors, sensors, GPS, and a Linux SBC (Raspberry Pi), serving as the hardware abstraction layer between physical components and the ROS software stack.

## Mainboard Variants

| Variant | Repository | Target Mower |
|---|---|---|
| Universal | hw-openmower-universal | Generic / new builds |
| YardForce | hw-openmower-yardforce | YardForce Classic 500 / SA650 |
| Sabo | hw-openmower-sabo | Sabo / John Deere mowers |

## Microcontroller: RP2040

### Specifications

- **Manufacturer**: Raspberry Pi Foundation
- **Architecture**: Dual-core ARM Cortex-M0+ @ 133 MHz
- **RAM**: 264 KB SRAM
- **Flash**: External (typically 2-16 MB via QSPI)
- **GPIO**: 30 multi-function pins
- **Communication**: 2x UART, 2x SPI, 2x I2C, 16x PWM channels
- **Special features**: 8x PIO (Programmable I/O) state machines
- **USB**: 1x USB 1.1 controller (device/host)
- **ADC**: 4-channel 12-bit SAR ADC
- **Power**: 1.8V–3.3V core, low-power sleep modes

### Dual-Core Utilization

- **Core 0**: Main application loop — service handling, sensor polling, communication
- **Core 1**: Time-critical tasks — motor control PWM, encoder reading, IMU sampling

## Communication Buses

### UART Interfaces

| UART | Connected Device | Baud Rate | Purpose |
|---|---|---|---|
| UART0 | Raspberry Pi | 115200 (V1) | V1: COBS-encoded command/status |
| UART1 | GPS module (u-blox) | 921600 | NMEA/UBX GNSS data stream |

**Note**: V2 firmware replaces UART0 serial communication with UDP over Ethernet (via `172.16.78.x` subnet between Pi and mainboard).

### SPI Interfaces

| SPI | Connected Device | Purpose |
|---|---|---|
| SPI0 | IMU (LSM6DSO) | Accelerometer + Gyroscope data |
| SPI1 | (available for expansion) | — |

### I2C Interfaces

| I2C | Connected Device | Purpose |
|---|---|---|
| I2C0 | BQ25756 Charger IC | Battery charging configuration |
| I2C0 | BMS (if present) | Cell-level battery monitoring |
| I2C1 | CoverUI Board | Button/LED user interface |

### Ethernet (V2 only)

- **Interface**: RP2040 PIO-based Ethernet or USB-Ethernet adapter
- **Subnet**: `172.16.78.0/24`
- **Protocol**: UDP multicast for xbot service discovery and data exchange
- **Bind IP**: `172.16.78.1` (configured in `openmower_defaults_v2.yaml`)

## Pin Assignments (Representative — YardForce Classic 500)

### Motor Control Pins

| Function | GPIO | Type |
|---|---|---|
| Left wheel ESC PWM | GPIOx | PWM output |
| Right wheel ESC PWM | GPIOx | PWM output |
| Mower blade ESC PWM | GPIOx | PWM output |
| Left encoder A/B | GPIOx | Digital input (PIO) |
| Right encoder A/B | GPIOx | Digital input (PIO) |

### Sensor Pins

| Function | GPIO | Type |
|---|---|---|
| Rain sensor | ADC channel | Analog input |
| Hall sensor 1-4 (lift/tilt) | GPIOx | Digital input |
| Bumper sensors | GPIOx | Digital input |
| Charge voltage sense | ADC channel | Analog input |
| System voltage sense | ADC channel | Analog input |
| Charging current sense | ADC channel | Analog input |

### Communication Pins

| Function | GPIO | Type |
|---|---|---|
| UART0 TX (to Pi) | GPIO0 | UART |
| UART0 RX (from Pi) | GPIO1 | UART |
| UART1 TX (to GPS) | GPIOx | UART |
| UART1 RX (from GPS) | GPIOx | UART |
| SPI0 SCK/MOSI/MISO/CS (IMU) | GPIOx | SPI |
| I2C0 SDA/SCL (Charger) | GPIOx | I2C |
| I2C1 SDA/SCL (CoverUI) | GPIOx | I2C |

### Power Control Pins

| Function | GPIO | Type |
|---|---|---|
| Raspberry Pi power enable | GPIOx | Digital output |
| ESC power enable | GPIOx | Digital output |
| GPS power enable | GPIOx | Digital output |
| Sound module (DFPlayer) TX | GPIOx | UART |

## Available GPIO for Expansion

The RP2040 has limited spare GPIO after the base system allocation. Expansion options:

1. **Unused PIO state machines**: Up to 4 available for custom protocols (e.g., WiFi module SPI/UART)
2. **SPI1**: Currently unassigned on most board variants
3. **Spare GPIO**: 2-4 pins available depending on board variant (check specific hardware schematic)
4. **USB**: Available for USB-connected peripherals (WiFi dongles at the Pi level)
5. **CoverUI I2C bus**: Could be extended with additional I2C devices

### WiFi Integration Options at Hardware Level

| Option | Interface | Pros | Cons |
|---|---|---|---|
| ESP32/ESP8266 module on SPI1 | SPI | Direct firmware access | Requires firmware driver, GPIO scarce |
| USB WiFi dongle on Pi | USB | No firmware changes | Handled at Linux/ROS level only |
| RP2040-W (Pico W variant) | On-chip | Native CYW43439 WiFi | Requires board redesign |
| UART-connected WiFi module | UART | Simple AT commands | Occupies UART, limited bandwidth |

## Power Architecture

```
AC/DC Adapter → BQ25756 Charger IC → Battery Pack (5S Li-ion typical)
                                         ↓
                                    System Bus (≈20V)
                                    ├── ESCs (motor power)
                                    ├── 5V regulator → Raspberry Pi
                                    ├── 3.3V regulator → RP2040 + sensors
                                    └── GPS module power
```

### Voltage Monitoring Points

- `v_charge`: Charger input voltage (presence = docked)
- `v_system` / `battery_voltage_adc`: Battery pack voltage
- `charging_current`: Current flowing into battery
- `batt_percentage`: Calculated from voltage thresholds

### Configurable Thresholds (from `openmower_defaults_v2.yaml`)

```yaml
services:
  power:
    battery_full_voltage: <model-specific>
    battery_empty_voltage: <model-specific>
    battery_critical_voltage: <model-specific>
    battery_critical_high_voltage: -1  # disabled
```

## Cross-References

- Firmware utilizing this hardware: [05-Firmware-Architecture.md](05-Firmware-Architecture.md)
- Communication protocols over these buses: [06-Communication-Protocols.md](06-Communication-Protocols.md)
- System-level view: [01-System-Architecture.md](01-System-Architecture.md)
