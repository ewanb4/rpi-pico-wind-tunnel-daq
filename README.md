# Raspberry Pi Pico Propulsion DAQ & Test Harness

An automated data acquisition (DAQ) and propulsion test-bench controller implemented in CircuitPython for a Raspberry Pi Pico. Developed for the Avionics Systems module at The University of Manchester.

## Overview
The system automates wind tunnel propulsion sweeps across stepped throttle points and airspeeds, sampling electrical and aerodynamic transducer channels while enforcing real-time hardware safety boundaries.

## Key Capabilities
- **Actuation:** Generates 50 Hz PWM signals (1000–2000 µs pulse widths) to drive an Electronic Speed Controller (ESC) across 10%–80% throttle steps.
- **Instrumentation & Multi-Bus Sensing:**
  - 16-bit ADC sampling for optical RPM (0–12,000 RPM), motor voltage (0–24.9 V), and current (0–40 A via 25 A/V sensitivity scaling).
  - UART serial decoding (<AA, BB.BBB, CC.CCC> frames at 9600 baud) for dynamic thrust and reaction torque load cells.
  - SPI interface for FAT-filesystem SD card logging with automated file incrementing (`DAS-X.csv`) and 5-second moving-average filtering.
- **Hardware Safety & HMI:**
  - Active pull-down Emergency Stop kill-switch routine.
  - Airspeed transition pause states with LED indicators.
  - Dual-frequency PWM buzzer alerts for low bus voltage (<22 V at 2000 Hz) and sustained over-current (>20 A at 500 Hz).

## Documentation
- `main.py`: Primary CircuitPython embedded firmware.
- `DAS_User_Manual.pdf`: Comprehensive system documentation, circuit pinout, and wiring schematics.
